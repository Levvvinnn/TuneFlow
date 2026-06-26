"""
Config Agent — proposes the starting configuration for a multi-agent run.

Its job ends after iteration 1. Every change after that is proposed by the
Optimizer Agent (agents/optimizer_agent.py) from the Judge's diagnosis, then
safety-checked by veto_node before being applied — see agents/graph.py.
"""
import json
from typing import Optional

from fireworks_client import config_agent_completion

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
