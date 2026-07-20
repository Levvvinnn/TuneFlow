"""
TuneFlow Orchestrator — thin FastAPI that the dashboard talks to.
Manages run lifecycle, polls status, returns history and comparison data.
"""
import os
import sys
import uuid
from contextlib import asynccontextmanager
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv()

# Add sibling packages to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "persistence"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "loadtest"))

# Direct imports — sys.path already extended above to include agents/ and persistence/
from database import init_persistence_db          # persistence/database.py
from store import (                                # persistence/store.py
    create_run,
    fail_run,
    finish_run,
    get_iterations,
    get_run,
    list_runs,
    save_iteration,
)
from graph import run_multi_agent                  # agents/graph.py
from baseline import run_baseline                  # agents/baseline.py
from termination import score_from_metrics         # agents/termination.py

# In-memory run status cache (supplements DB for live polling)
_run_status: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_persistence_db()
    yield


app = FastAPI(title="TuneFlow Orchestrator", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Request/Response schemas ──────────────────────────────────────────────────

class StartRunRequest(BaseModel):
    mode: str = "multi_agent"  # "multi_agent" | "baseline"
    max_iterations: int = 15
    plateau_n: int = 3
    target_p95_ms: Optional[float] = None
    vus: int = 100
    load_duration_seconds: int = 30
    load_repeats: int = 2

    # Multi-objective config. objective_weights partially overrides the
    # defaults {p95_latency_ms: 1.0, p99_latency_ms: 0.0, error_rate: 10000.0,
    # throughput_rps: 0.0} — latency/error weights add to the score (lower
    # metric = better), throughput weight subtracts (higher = better).
    # min_throughput_rps / max_error_rate are soft constraints: violations
    # add a large score penalty proportional to severity.
    # Example: minimize p95 but keep RPS above 80 and errors below 1%:
    #   {"objective_weights": {"p95_latency_ms": 1.0},
    #    "min_throughput_rps": 80, "max_error_rate": 0.01}
    objective_weights: Optional[dict] = None
    min_throughput_rps: Optional[float] = None
    max_error_rate: Optional[float] = None


class RunStatusResponse(BaseModel):
    run_id: str
    mode: str
    status: str
    current_iteration: int
    max_iterations: int
    termination_reason: Optional[str]
    latest_score: Optional[float]
    error: Optional[str] = None


class IterationResponse(BaseModel):
    id: str
    run_id: str
    iteration_number: int
    config_applied: Optional[dict]
    metrics: Optional[dict]
    judge_analysis: Optional[dict]
    judge_vision_analysis: Optional[dict]
    optimizer_proposal: Optional[dict]
    veto_event: Optional[dict]
    final_decision: Optional[dict]
    baseline_decision: Optional[dict]
    created_at: str


# ── Background task runners ───────────────────────────────────────────────────

async def _run_multi_agent_bg(run_id: str, req: StartRunRequest):
    _run_status[run_id] = {"status": "running", "current_iteration": 0, "latest_score": None}
    try:
        async def _status_update_save_fn(*args, **kwargs):
            """Wrap save_iteration to also update in-memory status."""
            it_num = kwargs.get("iteration_number", 0)
            metrics = kwargs.get("metrics", {})
            score = score_from_metrics(
                metrics, req.objective_weights, req.min_throughput_rps, req.max_error_rate
            )
            _run_status[run_id]["current_iteration"] = it_num
            _run_status[run_id]["latest_score"] = score
            return await save_iteration(*args, **kwargs)

        final = await run_multi_agent(
            run_id=run_id,
            max_iterations=req.max_iterations,
            plateau_n=req.plateau_n,
            target_p95_ms=req.target_p95_ms,
            vus=req.vus,
            load_duration_seconds=req.load_duration_seconds,
            load_repeats=req.load_repeats,
            save_iteration_fn=_status_update_save_fn,
            objective_weights=req.objective_weights,
            min_throughput_rps=req.min_throughput_rps,
            max_error_rate=req.max_error_rate,
        )
        if final.get("error"):
            # The graph caught its own exception in a node (config/judge/optimizer)
            # and routed straight to END, bypassing persist/terminate. That is a
            # failed run, not a finished one — surface it as such instead of
            # reporting "finished" with a null termination_reason.
            err = final["error"]
            await fail_run(uuid.UUID(run_id), err)
            _run_status[run_id]["status"] = "failed"
            _run_status[run_id]["error"] = err
            return

        reason = final.get("termination_reason") or "completed"
        await finish_run(uuid.UUID(run_id), reason)
        _run_status[run_id]["status"] = "finished"
        _run_status[run_id]["termination_reason"] = reason
    except Exception as e:
        await fail_run(uuid.UUID(run_id), str(e))
        _run_status[run_id]["status"] = "failed"
        _run_status[run_id]["error"] = str(e)


async def _run_baseline_bg(run_id: str, req: StartRunRequest):
    _run_status[run_id] = {"status": "running", "current_iteration": 0, "latest_score": None}
    try:
        async def _status_save_fn(*args, **kwargs):
            it_num = kwargs.get("iteration_number", 0)
            metrics = kwargs.get("metrics", {})
            score = score_from_metrics(
                metrics, req.objective_weights, req.min_throughput_rps, req.max_error_rate
            )
            _run_status[run_id]["current_iteration"] = it_num
            _run_status[run_id]["latest_score"] = score
            return await save_iteration(*args, **kwargs)

        result = await run_baseline(
            run_id=run_id,
            max_iterations=req.max_iterations,
            plateau_n=req.plateau_n,
            target_p95_ms=req.target_p95_ms,
            vus=req.vus,
            load_duration_seconds=req.load_duration_seconds,
            load_repeats=req.load_repeats,
            save_iteration_fn=_status_save_fn,
            objective_weights=req.objective_weights,
            min_throughput_rps=req.min_throughput_rps,
            max_error_rate=req.max_error_rate,
        )
        if result.get("error"):
            err = result["error"]
            await fail_run(uuid.UUID(run_id), err)
            _run_status[run_id]["status"] = "failed"
            _run_status[run_id]["error"] = err
            return

        reason = result.get("termination_reason") or "completed"
        await finish_run(uuid.UUID(run_id), reason)
        _run_status[run_id]["status"] = "finished"
        _run_status[run_id]["termination_reason"] = reason
    except Exception as e:
        await fail_run(uuid.UUID(run_id), str(e))
        _run_status[run_id]["status"] = "failed"
        _run_status[run_id]["error"] = str(e)


# ── Endpoints ─────────────────────────────────────────────────────────────────

ALLOWED_WEIGHT_KEYS = {"p95_latency_ms", "p99_latency_ms", "error_rate", "throughput_rps"}


@app.post("/runs", status_code=202)
async def start_run(req: StartRunRequest, background_tasks: BackgroundTasks):
    """Start a new tuning run (multi_agent or baseline) in the background."""
    if req.mode not in ("multi_agent", "baseline"):
        raise HTTPException(status_code=400, detail="mode must be 'multi_agent' or 'baseline'")

    # Validate objective config — a typo'd weight key would otherwise be
    # silently ignored and the run would optimize the wrong thing.
    if req.objective_weights:
        unknown = set(req.objective_weights) - ALLOWED_WEIGHT_KEYS
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=f"unknown objective_weights keys: {sorted(unknown)}; allowed: {sorted(ALLOWED_WEIGHT_KEYS)}",
            )
        bad_vals = {k: v for k, v in req.objective_weights.items() if not isinstance(v, (int, float)) or v < 0}
        if bad_vals:
            raise HTTPException(
                status_code=400,
                detail=f"objective_weights values must be non-negative numbers, got: {bad_vals}",
            )
    if req.min_throughput_rps is not None and req.min_throughput_rps <= 0:
        raise HTTPException(status_code=400, detail="min_throughput_rps must be > 0")
    if req.max_error_rate is not None and not (0 < req.max_error_rate <= 1):
        raise HTTPException(status_code=400, detail="max_error_rate must be in (0, 1]")

    run = await create_run(
        mode=req.mode,
        target_p95_ms=req.target_p95_ms,
        max_iterations=req.max_iterations,
        plateau_n=req.plateau_n,
        vus=req.vus,
        load_duration_seconds=req.load_duration_seconds,
        load_repeats=req.load_repeats,
    )
    run_id = str(run.id)

    if req.mode == "multi_agent":
        background_tasks.add_task(_run_multi_agent_bg, run_id, req)
    else:
        background_tasks.add_task(_run_baseline_bg, run_id, req)

    return {"run_id": run_id, "mode": req.mode, "status": "started"}


@app.get("/runs/{run_id}/status", response_model=RunStatusResponse)
async def get_run_status(run_id: str):
    run = await get_run(uuid.UUID(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    mem = _run_status.get(run_id, {})
    return RunStatusResponse(
        run_id=run_id,
        mode=run.mode,
        status=mem.get("status", run.status),
        current_iteration=mem.get("current_iteration", 0),
        max_iterations=run.max_iterations,
        termination_reason=mem.get("termination_reason", run.termination_reason),
        latest_score=mem.get("latest_score"),
        error=mem.get("error"),
    )


@app.get("/runs/{run_id}/history")
async def get_run_history(run_id: str):
    run = await get_run(uuid.UUID(run_id))
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    iterations = await get_iterations(uuid.UUID(run_id))
    return {
        "run_id": run_id,
        "mode": run.mode,
        "status": run.status,
        "termination_reason": run.termination_reason,
        "iterations": [
            {
                "id": str(it.id),
                "run_id": str(it.run_id),
                "iteration_number": it.iteration_number,
                "config_applied": it.config_applied,
                "metrics": it.metrics,
                "judge_analysis": it.judge_analysis,
                "judge_vision_analysis": it.judge_vision_analysis,
                "optimizer_proposal": it.optimizer_proposal,
                "veto_event": it.veto_event,
                "final_decision": it.final_decision,
                "baseline_decision": it.baseline_decision,
                "created_at": it.created_at.isoformat() if it.created_at else None,
            }
            for it in iterations
        ],
    }


@app.get("/compare")
async def compare_runs(run_a: str, run_b: str):
    """Return both runs' iteration data for side-by-side comparison."""
    runs = {}
    for rid in (run_a, run_b):
        run = await get_run(uuid.UUID(rid))
        if run is None:
            raise HTTPException(status_code=404, detail=f"Run {rid} not found")
        iterations = await get_iterations(uuid.UUID(rid))
        runs[rid] = {
            "run_id": rid,
            "mode": run.mode,
            "status": run.status,
            "termination_reason": run.termination_reason,
            "iterations": [
                {
                    "iteration_number": it.iteration_number,
                    "p95_latency_ms": (it.metrics or {}).get("p95_latency_ms"),
                    "p99_latency_ms": (it.metrics or {}).get("p99_latency_ms"),
                    "throughput_rps": (it.metrics or {}).get("throughput_rps"),
                    "error_rate": (it.metrics or {}).get("error_rate"),
                    "config_applied": it.config_applied,
                    "has_veto": bool((it.veto_event or {}).get("vetoed")),
                }
                for it in iterations
            ],
        }
    return {"run_a": runs[run_a], "run_b": runs[run_b]}


@app.get("/runs")
async def list_all_runs():
    runs = await list_runs()
    return [
        {
            "run_id": str(r.id),
            "mode": r.mode,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
            "termination_reason": r.termination_reason,
        }
        for r in runs
    ]


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    host = os.getenv("ORCHESTRATOR_HOST", "0.0.0.0")
    port = int(os.getenv("ORCHESTRATOR_PORT", "8080"))
    uvicorn.run("main:app", host=host, port=port, reload=False)

