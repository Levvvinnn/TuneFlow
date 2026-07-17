"""
Judge Agent:
  1. Applies proposed config via hot-swap endpoint
  2. Runs load test (N repeats)
  3. Diagnoses bottleneck via text analysis + vision analysis of rendered chart
  4. Holds veto power over Optimizer proposals (max 1 revision per iteration)
  5. Disagreement-based abstention (DBA): a second, *direct* single-shot diagnosis
     is compared against the decomposed pipeline's diagnosis; if the two disagree
     on the bottleneck, the belief is treated as fragile and the iteration
     abstains from changing the config. Based on "Decomposed Prompting Does Not
     Fix Knowledge Gaps, But Helps Models Say 'I Don't Know'" (arXiv:2602.04853).
"""
import asyncio
import json
import os
import sys
import tempfile
from typing import Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loadtest"))
from runner import run_load_test_with_repeats

from chart import render_performance_chart
from config_agent import PARAM_BOUNDS
from fireworks_client import json_completion, text_completion, vision_completion

SERVICE_URL = os.getenv("SERVICE_HOST", "http://localhost:8000")

JUDGE_SYSTEM = (
    "You are a database and backend performance diagnostics expert. "
    "Analyze load test metrics and identify the primary bottleneck. "
    "Be precise and actionable."
)

# ── Disagreement-Based Abstention (DBA) ──────────────────────────────────────
# arXiv:2602.04853: cross-regime disagreement between a direct (single-shot)
# answer and a decomposed answer is a precise signal of a fragile belief.
# When the two diagnoses disagree, abstain (keep current config) instead of
# applying an uncertain change. Toggle via env; enabled by default.

def dba_enabled() -> bool:
    return os.getenv("DBA_ABSTENTION", "true").strip().lower() in ("1", "true", "yes", "on")


def dba_shadow_mode() -> bool:
    """
    Shadow mode: still compute and record the disagreement check, but do NOT
    abstain — let the Optimizer's proposal through as normal. This exists
    purely to collect evaluation data: real abstention keeps the config
    unchanged, so there is no way to tell, after the fact, whether the
    decomposed diagnosis the model disagreed with would actually have been
    right. Shadow mode lets both agreement and disagreement iterations run to
    completion so scripts/analyze_dba_outcomes.py can measure, empirically,
    whether disagreement iterations produce worse outcomes than agreement
    iterations — instead of assuming it either way.
    """
    return os.getenv("DBA_SHADOW_MODE", "false").strip().lower() in ("1", "true", "yes", "on")


def check_diagnosis_agreement(direct: Optional[dict], decomposed: Optional[dict]) -> tuple[bool, str]:
    """
    Compare the direct single-shot diagnosis with the decomposed pipeline diagnosis.

    Returns (agree, reason). Missing or "unknown" diagnoses are treated as
    non-comparable → agree=True (we only abstain on a *confident* conflict,
    mirroring the paper's use of disagreement — not absence — as the signal).
    """
    d = (direct or {}).get("bottleneck")
    c = (decomposed or {}).get("bottleneck")
    if not d or not c or d == "unknown" or c == "unknown":
        return True, "not comparable (missing or unknown diagnosis) — no abstention"
    if d == c:
        return True, f"direct and decomposed diagnoses agree on '{c}'"
    return (
        False,
        f"direct diagnosis '{d}' disagrees with decomposed diagnosis '{c}' — "
        "fragile belief, abstaining this iteration (DBA, arXiv:2602.04853)",
    )


# Safety constraints for veto decisions
SAFETY_CONSTRAINTS = {
    "pool_size": {"min": 2, "reason": "Pool size below 2 causes immediate starvation under any load"},
    "query_timeout_ms": {
        "min": 500,
        "reason": "Timeout below 500ms causes cascading errors without revealing useful info",
    },
    "retry_interval_ms": {"min": 10, "reason": "Retry interval below 10ms creates retry storms"},
}


async def apply_config(config: dict) -> dict:
    """POST to /admin/reconfigure and return the response.

    Whitelists the five tunable parameters so that metadata keys added by
    the Optimizer Agent (rationale, change_summary, expected_effect, etc.)
    are never forwarded to the service endpoint.
    """
    payload = {k: v for k, v in config.items() if k in PARAM_BOUNDS}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{SERVICE_URL}/admin/reconfigure", json=payload)
        resp.raise_for_status()
        return resp.json()


async def run_and_measure(
    vus: int = 100,
    duration_seconds: int = 30,
    repeats: int = 2,
) -> dict:
    """Apply load test and return metrics dict."""
    metrics = run_load_test_with_repeats(
        vus=vus,
        duration_seconds=duration_seconds,
        repeats=repeats,
        service_url=SERVICE_URL,
    )
    return metrics.to_dict()


async def diagnose_text(metrics: dict, config_applied: dict, iteration_history: list[dict]) -> dict:
    """Text-based bottleneck diagnosis using structured metrics."""
    history_summary = [
        {
            "iteration": h.get("iteration_number"),
            "p95_ms": h.get("p95_latency_ms"),
            "rps": h.get("throughput_rps"),
            "error_rate": h.get("error_rate"),
            "config": h.get("config_applied"),
        }
        for h in iteration_history[-5:]
    ]

    prompt = f"""
Analyze these load test metrics for a FastAPI + PostgreSQL service:

Current metrics:
{json.dumps(metrics, indent=2)}

Config applied for this iteration:
{json.dumps(config_applied, indent=2)}

Recent iteration history:
{json.dumps(history_summary, indent=2)}

Diagnose the PRIMARY performance bottleneck. Consider:
- If p95 latency is high but error_rate is low → likely pool exhaustion or slow queries
- If error_rate is high → likely pool exhaustion or timeout too aggressive
- If throughput is low but latency is OK → likely VU/connection limit
- Trend: is performance improving, degrading, or oscillating?

Return a JSON object with:
  bottleneck: str (one of: "pool_exhaustion", "slow_queries", "timeout_too_aggressive",
                   "cache_miss", "batch_inefficiency", "no_bottleneck", "unknown")
  severity: str ("low" | "medium" | "high")
  reasoning: str (2-3 sentences explaining the diagnosis)
  recommended_direction: dict (which parameters to change and in which direction, e.g.
                          {{"pool_size": "increase", "cache_ttl_seconds": "increase"}})
  trend: str ("improving" | "degrading" | "oscillating" | "stable")
"""
    try:
        return await json_completion(prompt, JUDGE_SYSTEM, temperature=0.1)
    except ValueError as e:
        # json_completion raises ValueError when the model's response isn't valid JSON.
        # Return a safe fallback so the loop continues rather than crashing.
        return {
            "bottleneck": "unknown",
            "severity": "medium",
            "reasoning": str(e)[:500],
            "recommended_direction": {},
            "trend": "unknown",
        }


async def diagnose_direct(metrics: dict, config_applied: dict, iteration_history: list[dict]) -> dict:
    """
    DIRECT diagnosis regime (DBA, arXiv:2602.04853).

    Task-equivalent to diagnose_text — same inputs, same output schema — but with
    NO diagnostic scaffold: no signal-by-signal walkthrough, no decision rules,
    just the raw question. Cross-checking this direct answer against the
    decomposed diagnosis exposes fragile beliefs: stable knowledge answers the
    same under both regimes, hallucinations are stochastic and diverge.
    """
    history_summary = [
        {
            "iteration": h.get("iteration_number"),
            "p95_ms": h.get("p95_latency_ms"),
            "rps": h.get("throughput_rps"),
            "error_rate": h.get("error_rate"),
            "config": h.get("config_applied"),
        }
        for h in iteration_history[-5:]
    ]

    prompt = f"""
What is the PRIMARY performance bottleneck of this FastAPI + PostgreSQL service?

Current metrics:
{json.dumps(metrics, indent=2)}

Config applied for this iteration:
{json.dumps(config_applied, indent=2)}

Recent iteration history:
{json.dumps(history_summary, indent=2)}

Return a JSON object with:
  bottleneck: str (one of: "pool_exhaustion", "slow_queries", "timeout_too_aggressive",
                   "cache_miss", "batch_inefficiency", "no_bottleneck", "unknown")
  reasoning: str (1 sentence)
"""
    try:
        return await json_completion(prompt, JUDGE_SYSTEM, temperature=0.1)
    except ValueError as e:
        return {"bottleneck": "unknown", "reasoning": str(e)[:200]}


async def diagnose_vision(chart_path: str, metrics: dict) -> dict:
    """Vision-based diagnosis using rendered chart image — adds a second signal."""
    prompt = f"""
This chart has three stacked panels for a FastAPI + PostgreSQL service across multiple
tuning iterations, top to bottom: (1) Latency — p95 and p99, (2) Throughput — req/s,
(3) Error Rate — %.

Latest metrics for context:
- p95 latency: {metrics.get('p95_latency_ms', 'N/A')} ms
- throughput: {metrics.get('throughput_rps', 'N/A')} req/s
- error rate: {metrics.get('error_rate', 'N/A')}

Analyze each panel SEPARATELY — do not let one panel's shape bleed into another
field's label. In particular, `visual_pattern` below describes the LATENCY panel only
(it is latency, not throughput, that is being optimized) and must agree with
`latency_trend`: e.g. if latency_trend is "degrading", visual_pattern must be a
decline/worsening shape, never an "_improvement" label, even if throughput happens to
be improving in its own panel.

1. Latency panel: is it trending down (improving), up (degrading), or oscillating? Is
   the change gradual or a sudden step?
2. Throughput panel: step-change or gradual change, and in which direction?
3. Error-rate panel: are spikes visible, and when do they occur?
4. What does the overall picture suggest about the tuning direction?

Return a JSON object with:
  visual_pattern: str — shape of the LATENCY panel only, one of: "gradual_decline"
                   (improving), "gradual_increase" (degrading), "sudden_step_improvement",
                   "sudden_step_regression", "oscillating", "flat", "spike_then_recovery"
  latency_trend: str ("improving" | "degrading" | "oscillating" | "flat") — must agree
                   with visual_pattern's direction
  throughput_trend: str ("improving" | "degrading" | "oscillating" | "flat")
  error_pattern: str ("none" | "spikes" | "steady" | "declining")
  visual_insight: str (1-2 sentences: what the visual pattern suggests for next step)
"""
    try:
        raw = await vision_completion(prompt, chart_path, temperature=0.1)
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            raw = raw.rsplit("```", 1)[0].strip()
        return json.loads(raw)
    except Exception as e:
        return {"error": str(e), "visual_insight": "Vision analysis unavailable"}


def check_safety_constraints(proposal: dict) -> tuple[bool, str]:
    """
    Returns (is_safe, reason). Vetos if any parameter violates minimum safety thresholds.
    """
    for param, constraint in SAFETY_CONSTRAINTS.items():
        val = proposal.get(param)
        if val is None:
            continue
        if "min" in constraint and val < constraint["min"]:
            return (
                False,
                f"{param}={val} violates minimum {constraint['min']}: {constraint['reason']}",
            )
        if "max" in constraint and val > constraint["max"]:
            return (
                False,
                f"{param}={val} violates maximum {constraint['max']}: {constraint['reason']}",
            )
    return True, ""


async def full_judge_cycle(
    proposed_config: dict,
    iteration_history: list[dict],
    vus: int = 100,
    duration_seconds: int = 30,
    repeats: int = 2,
) -> dict:
    """
    Full Judge cycle:
    1. Apply config
    2. Run load test
    3. Text diagnosis (decomposed) + direct diagnosis (DBA cross-check), concurrent
    4. Vision diagnosis (best-effort — won't block if vision API fails)
    Returns a dict with all Judge outputs.
    """
    # 1. Apply config
    apply_result = await apply_config(proposed_config)

    # 2. Run load test
    metrics = await run_and_measure(vus=vus, duration_seconds=duration_seconds, repeats=repeats)

    # 3. Decomposed text diagnosis + direct diagnosis (concurrent — no added latency).
    #    The direct call is only made when DBA abstention is enabled.
    direct_diag = None
    if dba_enabled():
        text_diag, direct_diag = await asyncio.gather(
            diagnose_text(metrics, proposed_config, iteration_history),
            diagnose_direct(metrics, proposed_config, iteration_history),
        )
    else:
        text_diag = await diagnose_text(metrics, proposed_config, iteration_history)

    # 4. Vision diagnosis — build chart and analyze
    vision_diag = None
    chart_data = []
    for h in iteration_history:
        chart_data.append({
            "iteration_number": h.get("iteration_number"),
            "p95_latency_ms": h.get("p95_latency_ms", 0),
            "p99_latency_ms": h.get("p99_latency_ms", 0),
            "throughput_rps": h.get("throughput_rps", 0),
            "error_rate": h.get("error_rate", 0),
            "config_applied": h.get("config_applied", {}),
        })
    # Add current iteration (approximate — real metrics just measured)
    chart_data.append({
        "iteration_number": len(iteration_history) + 1,
        "p95_latency_ms": metrics.get("p95_latency_ms", 0),
        "p99_latency_ms": metrics.get("p99_latency_ms", 0),
        "throughput_rps": metrics.get("throughput_rps", 0),
        "error_rate": metrics.get("error_rate", 0),
        "config_applied": proposed_config,
    })

    chart_path = render_performance_chart(chart_data)
    if chart_path:
        try:
            vision_diag = await diagnose_vision(chart_path, metrics)
            # Incorporate vision insight into text diagnosis if available
            if vision_diag and "visual_insight" in vision_diag:
                text_diag["vision_supplement"] = vision_diag["visual_insight"]
                text_diag["visual_pattern"] = vision_diag.get("visual_pattern", "unknown")
        except Exception as e:
            vision_diag = {"error": str(e), "visual_insight": "Vision analysis failed"}
        finally:
            try:
                os.unlink(chart_path)
            except Exception:
                pass

    # Record the DBA cross-check inside text_diagnosis so it persists with
    # judge_analysis without any DB schema change.
    if direct_diag is not None:
        agree, agree_reason = check_diagnosis_agreement(direct_diag, text_diag)
        text_diag["direct_check"] = {
            "bottleneck": direct_diag.get("bottleneck"),
            "agrees": agree,
            "detail": agree_reason,
        }

    return {
        "metrics": metrics,
        "config_applied": proposed_config,
        "apply_result": apply_result,
        "text_diagnosis": text_diag,
        "direct_diagnosis": direct_diag,
        "vision_diagnosis": vision_diag,
    }
