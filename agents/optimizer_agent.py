"""
Optimizer Agent:
  - Takes Judge's text + vision analysis
  - Proposes the next config change (using the stronger Fireworks optimizer model)
  - Handles veto by revising the proposal (bounded to exactly 1 retry)
"""
import json

from config_agent import PARAM_BOUNDS, clamp_config
from fireworks_client import optimizer_completion

SYSTEM = (
    "You are a backend performance optimization strategist. "
    "Based on bottleneck analysis, decide which configuration parameter to change "
    "and in which direction to maximize throughput while minimizing p95 latency. "
    "Consider tradeoffs carefully. Return valid JSON only."
)


async def propose_next_config(
    current_config: dict,
    judge_output: dict,
    iteration_history: list[dict],
) -> dict:
    """Propose the next config based on Judge's diagnosis."""
    text_diag = judge_output.get("text_diagnosis", {})
    vision_diag = judge_output.get("vision_diagnosis") or {}
    metrics = judge_output.get("metrics", {})

    history_summary = [
        {
            "iter": h.get("iteration_number"),
            "p95": h.get("p95_latency_ms"),
            "rps": h.get("throughput_rps"),
            "err": h.get("error_rate"),
            "config": h.get("config_applied"),
        }
        for h in iteration_history[-6:]
    ]

    prompt = f"""
Current service configuration:
{json.dumps(current_config, indent=2)}

Last load test metrics:
  p95_latency_ms: {metrics.get('p95_latency_ms')}
  p99_latency_ms: {metrics.get('p99_latency_ms')}
  throughput_rps: {metrics.get('throughput_rps')}
  error_rate: {metrics.get('error_rate')}
  db_connection_count: {metrics.get('db_connection_count')}

Judge's bottleneck diagnosis:
  bottleneck: {text_diag.get('bottleneck')}
  severity: {text_diag.get('severity')}
  reasoning: {text_diag.get('reasoning')}
  recommended_direction: {json.dumps(text_diag.get('recommended_direction', {}))}
  trend: {text_diag.get('trend')}

Visual pattern (from chart analysis):
  visual_pattern: {vision_diag.get('visual_pattern', 'N/A')}
  visual_insight: {vision_diag.get('visual_insight', 'N/A')}

Recent iteration history:
{json.dumps(history_summary, indent=2)}

Parameter bounds:
{json.dumps(PARAM_BOUNDS, indent=2)}

Based on this analysis, propose ONE targeted configuration change that will most improve
performance in the next iteration. Avoid reversing a change that just improved performance.

Return JSON with ALL config parameters (change at most 2 per iteration) plus:
  "change_summary": str (which param changed and in which direction)
  "expected_effect": str (what outcome you expect and why)
  "rationale": str (why this change addresses the identified bottleneck)
"""
    result = await optimizer_completion(prompt, SYSTEM)
    rationale = result.pop("rationale", "")
    change_summary = result.pop("change_summary", "")
    expected_effect = result.pop("expected_effect", "")
    clamped = clamp_config(result)
    clamped["rationale"] = rationale
    clamped["change_summary"] = change_summary
    clamped["expected_effect"] = expected_effect
    return clamped


async def revise_proposal(
    original_proposal: dict,
    veto_reason: str,
    current_config: dict,
    judge_output: dict,
    iteration_history: list[dict],
) -> dict:
    """
    Respond to a veto with a revised proposal.
    This is the SINGLE allowed revision — the caller enforces the round limit.
    """
    text_diag = judge_output.get("text_diagnosis", {})
    metrics = judge_output.get("metrics", {})

    prompt = f"""
Your previous configuration proposal was VETOED by the Judge Agent.

Original (vetoed) proposal:
{json.dumps({k: v for k, v in original_proposal.items() if k not in ['rationale','change_summary','expected_effect']}, indent=2)}

Veto reason: {veto_reason}

Current configuration:
{json.dumps(current_config, indent=2)}

Judge's bottleneck analysis:
  bottleneck: {text_diag.get('bottleneck')}
  reasoning: {text_diag.get('reasoning')}

Last metrics:
  p95_latency_ms: {metrics.get('p95_latency_ms')}
  error_rate: {metrics.get('error_rate')}

Parameter bounds:
{json.dumps(PARAM_BOUNDS, indent=2)}

Propose a REVISED configuration that avoids the safety violation.
Stay within the parameter bounds and address the veto reason directly.

Return JSON with all config parameters plus:
  "rationale": str
  "change_summary": str
  "revision_note": str (how you addressed the veto)
"""
    result = await optimizer_completion(prompt, SYSTEM)
    for key in ["rationale", "change_summary", "revision_note"]:
        result.setdefault(key, "")
    clamped = clamp_config({k: v for k, v in result.items() if k in PARAM_BOUNDS})
    for key in ["rationale", "change_summary", "revision_note"]:
        clamped[key] = result.get(key, "")
    return clamped
