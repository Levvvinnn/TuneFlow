"""
Judge Agent:
  1. Applies proposed config via hot-swap endpoint
  2. Runs load test (N repeats)
  3. Diagnoses bottleneck via text analysis + vision analysis of rendered chart
  4. Holds veto power over Optimizer proposals (max 1 revision per iteration)
"""
import json
import os
import sys
import tempfile
from typing import Optional

import httpx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loadtest"))
from runner import run_load_test_with_repeats

from chart import render_performance_chart
from qwen_client import text_completion, vision_completion

SERVICE_URL = os.getenv("SERVICE_HOST", "http://localhost:8000")

JUDGE_SYSTEM = (
    "You are a database and backend performance diagnostics expert. "
    "Analyze load test metrics and identify the primary bottleneck. "
    "Be precise and actionable."
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
    """POST to /admin/reconfigure and return the response."""
    payload = {k: v for k, v in config.items() if k != "rationale"}
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
    raw = await text_completion(prompt, JUDGE_SYSTEM, temperature=0.1)
    # Parse JSON from response
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1] if "\n" in raw else raw
        raw = raw.rsplit("```", 1)[0].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "bottleneck": "unknown",
            "severity": "medium",
            "reasoning": raw[:500],
            "recommended_direction": {},
            "trend": "unknown",
        }


async def diagnose_vision(chart_path: str, metrics: dict) -> dict:
    """Vision-based diagnosis using rendered chart image — adds a second signal."""
    prompt = f"""
This chart shows performance metrics (p95 latency, throughput, error rate) across
multiple tuning iterations for a FastAPI + PostgreSQL service.

Latest metrics for context:
- p95 latency: {metrics.get('p95_latency_ms', 'N/A')} ms
- throughput: {metrics.get('throughput_rps', 'N/A')} req/s
- error rate: {metrics.get('error_rate', 'N/A')}

Analyze the VISUAL PATTERN of the charts:
1. Is latency trending down (improving), up (degrading), or oscillating?
2. Does throughput show a step-change or a gradual improvement?
3. Are error spikes visible and when do they occur?
4. What does the visual pattern suggest about the tuning direction?

Return a JSON object with:
  visual_pattern: str (e.g., "slow_decline", "sudden_step_improvement", "oscillating",
                   "flat", "spike_then_recovery")
  latency_trend: str ("improving" | "degrading" | "oscillating" | "flat")
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
    3. Text diagnosis
    4. Vision diagnosis (best-effort — won't block if vision API fails)
    Returns a dict with all Judge outputs.
    """
    # 1. Apply config
    apply_result = await apply_config(proposed_config)

    # 2. Run load test
    metrics = await run_and_measure(vus=vus, duration_seconds=duration_seconds, repeats=repeats)

    # 3. Text diagnosis
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

    return {
        "metrics": metrics,
        "config_applied": proposed_config,
        "apply_result": apply_result,
        "text_diagnosis": text_diag,
        "vision_diagnosis": vision_diag,
    }
