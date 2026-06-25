"""
Baseline "god agent" mode — a single Qwen call per iteration that does
propose + diagnose + decide in one shot. Runs with the same iteration budget,
load pattern, and termination logic as the multi-agent run.

This is the single-agent baseline for Track 3 head-to-head comparison.
"""
import asyncio
import json
import os
import sys
import uuid
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loadtest"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "persistence"))

import httpx
from runner import run_load_test_with_repeats

from config_agent import DEFAULT_CONFIG, PARAM_BOUNDS, clamp_config
from qwen_client import baseline_god_agent_completion
from termination import check_termination, score_from_metrics

SERVICE_URL = os.getenv("SERVICE_HOST", "http://localhost:8000")

SYSTEM = (
    "You are a backend performance optimization expert. In a single analysis, "
    "you will (1) diagnose the current bottleneck from metrics, "
    "(2) propose a configuration change to improve performance, and "
    "(3) explain your decision. Return valid JSON only."
)


async def apply_config(config: dict):
    payload = {k: v for k, v in config.items() if k in PARAM_BOUNDS}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(f"{SERVICE_URL}/admin/reconfigure", json=payload)
        resp.raise_for_status()
        return resp.json()


async def god_agent_step(
    current_config: dict,
    metrics: Optional[dict],
    iteration_history: list[dict],
    iteration_number: int,
) -> dict:
    """Single Qwen call: diagnose + propose next config in one shot."""
    history_summary = [
        {
            "iter": h.get("iteration_number"),
            "p95": h.get("p95_latency_ms"),
            "rps": h.get("throughput_rps"),
            "err": h.get("error_rate"),
            "config": h.get("config_applied"),
        }
        for h in iteration_history[-5:]
    ]

    metrics_block = json.dumps(metrics or {}, indent=2) if metrics else "No metrics yet (iteration 1)"

    prompt = f"""
You are tuning a FastAPI + PostgreSQL service. This is iteration {iteration_number}.

Current configuration:
{json.dumps(current_config, indent=2)}

Last load test metrics:
{metrics_block}

Recent iteration history:
{json.dumps(history_summary, indent=2)}

Parameter bounds:
{json.dumps(PARAM_BOUNDS, indent=2)}

In ONE response:
1. Diagnose the primary bottleneck
2. Propose the complete next configuration (change at most 2 parameters)
3. Explain your decision

Return a JSON object with:
  bottleneck: str (e.g., "pool_exhaustion", "slow_queries", "cache_miss", "no_bottleneck")
  diagnosis: str (2 sentences)
  next_config: dict (all parameter keys with new values, within bounds)
  rationale: str (why you chose these values)
  expected_improvement: str (what you expect to happen)
"""
    result = await baseline_god_agent_completion(prompt, SYSTEM)

    next_config_raw = result.pop("next_config", current_config)
    clamped = clamp_config(next_config_raw)
    result["next_config"] = clamped
    return result


async def run_baseline(
    run_id: str,
    max_iterations: int = 15,
    plateau_n: int = 3,
    target_p95_ms: Optional[float] = None,
    vus: int = 100,
    load_duration_seconds: int = 30,
    load_repeats: int = 2,
    save_iteration_fn=None,
) -> dict:
    """
    Run the single-agent baseline loop.
    Same termination logic and load pattern as multi-agent — fair comparison.
    """
    current_config = DEFAULT_CONFIG.copy()
    scores = []
    iteration_history = []
    termination_reason = None
    last_metrics = None
    error = None

    for iteration_number in range(1, max_iterations + 1):
        print(f"[baseline] Iteration {iteration_number}/{max_iterations}")

        # Apply current config
        try:
            await apply_config(current_config)
        except Exception as e:
            print(f"[baseline] Config apply failed: {e}", flush=True)
            error = f"Config apply failed: {e}"
            break

        # Run load test
        try:
            m = run_load_test_with_repeats(
                vus=vus,
                duration_seconds=load_duration_seconds,
                repeats=load_repeats,
                service_url=SERVICE_URL,
            )
            last_metrics = m.to_dict()
        except Exception as e:
            print(f"[baseline] Load test failed: {e}", flush=True)
            error = f"Load test failed: {e}"
            break

        # Single god-agent call: diagnose + propose
        try:
            decision = await god_agent_step(
                current_config=current_config,
                metrics=last_metrics,
                iteration_history=iteration_history,
                iteration_number=iteration_number,
            )
        except Exception as e:
            print(f"[baseline] God agent failed: {e}", flush=True)
            decision = {"bottleneck": "error", "diagnosis": str(e), "next_config": current_config}

        score = score_from_metrics(last_metrics)
        scores.append(score)

        iteration_entry = {
            "iteration_number": iteration_number,
            "p95_latency_ms": last_metrics.get("p95_latency_ms", 0),
            "p99_latency_ms": last_metrics.get("p99_latency_ms", 0),
            "throughput_rps": last_metrics.get("throughput_rps", 0),
            "error_rate": last_metrics.get("error_rate", 0),
            "config_applied": current_config.copy(),
        }
        iteration_history.append(iteration_entry)

        # Persist
        if save_iteration_fn:
            try:
                await save_iteration_fn(
                    run_id=uuid.UUID(run_id),
                    iteration_number=iteration_number,
                    config_applied=current_config,
                    metrics=last_metrics,
                    baseline_decision=decision,
                )
            except Exception:
                pass

        # Termination check — identical logic as multi-agent
        term = check_termination(
            iteration_number=iteration_number,
            scores=scores,
            max_iterations=max_iterations,
            plateau_n=plateau_n,
            target_score=target_p95_ms,
        )
        if term.should_stop:
            termination_reason = term.reason
            break

        # Next iteration: use god agent's proposed config
        next_cfg_raw = decision.get("next_config", current_config)
        current_config = clamp_config(next_cfg_raw) if isinstance(next_cfg_raw, dict) else current_config

    return {
        "run_id": run_id,
        "mode": "baseline",
        "total_iterations": len(iteration_history),
        # Only fall back to "max_iterations" when the loop actually ran to
        # completion without a hard error — an error that broke the loop early
        # should never be silently relabeled as a normal termination reason.
        "termination_reason": termination_reason or ("max_iterations" if error is None else None),
        "final_config": current_config,
        "final_score": scores[-1] if scores else None,
        "scores": scores,
        "error": error,
    }
