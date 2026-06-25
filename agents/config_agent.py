"""Config Agent — proposes the initial config and targeted per-iteration changes."""
import json
from typing import Optional

from qwen_client import config_agent_completion

SYSTEM = (
    "You are a backend configuration specialist. Your job is to propose database "
    "connection pool and query configuration values that maximize throughput and "
    "minimize p95 latency under a steady load test. Respond with valid JSON only."
)

# Reasonable bounds for each tunable parameter
PARAM_BOUNDS = {
    "pool_size": (2, 50),
    "query_timeout_ms": (500, 15000),
    "cache_ttl_seconds": (5, 600),
    "batch_size": (10, 2000),
    "retry_interval_ms": (10, 2000),
}

DEFAULT_CONFIG = {
    "pool_size": 5,
    "query_timeout_ms": 5000,
    "cache_ttl_seconds": 60,
    "batch_size": 100,
    "retry_interval_ms": 100,
}


def clamp_config(cfg: dict) -> dict:
    """Clamp each parameter to its valid range."""
    out = {}
    for k, v in cfg.items():
        if k in PARAM_BOUNDS:
            lo, hi = PARAM_BOUNDS[k]
            out[k] = max(lo, min(hi, int(v)))
        else:
            out[k] = v
    return out


async def propose_initial_config() -> dict:
    """Iteration 1: propose a sensible baseline config."""
    prompt = f"""
Propose an initial database connection pool configuration for a FastAPI + PostgreSQL service
that will be load-tested at ~100 concurrent virtual users.

The configurable parameters and their allowed ranges are:
{json.dumps(PARAM_BOUNDS, indent=2)}

Return a JSON object with these exact keys: pool_size, query_timeout_ms, cache_ttl_seconds,
batch_size, retry_interval_ms.

Choose values that are a reasonable starting point — neither too conservative nor too aggressive.
"""
    result = await config_agent_completion(prompt, SYSTEM)
    return clamp_config(result)


async def propose_config_change(
    current_config: dict,
    judge_analysis: dict,
    iteration_history: list[dict],
) -> dict:
    """
    Given the Judge's bottleneck analysis and history, propose a targeted config change.
    Returns the full config dict with one or two parameters changed.
    """
    history_summary = []
    for h in iteration_history[-5:]:  # last 5 iterations for context
        history_summary.append({
            "iteration": h.get("iteration_number"),
            "config": h.get("config_applied"),
            "p95_ms": h.get("p95_latency_ms"),
            "rps": h.get("throughput_rps"),
            "error_rate": h.get("error_rate"),
        })

    prompt = f"""
You are tuning a FastAPI + PostgreSQL service. Here is the current configuration:
{json.dumps(current_config, indent=2)}

The Judge Agent's bottleneck analysis for the last iteration:
{json.dumps(judge_analysis, indent=2)}

Recent iteration history (last 5):
{json.dumps(history_summary, indent=2)}

Parameter bounds:
{json.dumps(PARAM_BOUNDS, indent=2)}

Based on the bottleneck analysis, propose the SINGLE MOST IMPACTFUL change to improve p95 latency
and throughput. Return the COMPLETE config JSON with all parameters, changing only what is
necessary. Include a "rationale" field explaining which parameter you changed and why.

Return JSON with keys: pool_size, query_timeout_ms, cache_ttl_seconds, batch_size,
retry_interval_ms, rationale.
"""
    result = await config_agent_completion(prompt, SYSTEM)
    rationale = result.pop("rationale", "")
    clamped = clamp_config(result)
    clamped["rationale"] = rationale
    return clamped
