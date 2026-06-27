"""Access layer for persistence DB — all reads and writes go through here."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select

from database import get_session
from models import Iteration, Run

async def create_run(
    mode: str,
    target_p95_ms: Optional[float] = None,
    max_iterations: int = 10,
    plateau_n: int = 3,
    vus: int = 100,
    load_duration_seconds: int = 30,
    load_repeats: int = 2,
) -> Run:
    async with get_session() as session:
        run = Run(
            id=uuid.uuid4(),
            mode=mode,
            status="running",
            target_p95_ms=target_p95_ms,
            max_iterations=max_iterations,
            plateau_n=plateau_n,
            vus=vus,
            load_duration_seconds=load_duration_seconds,
            load_repeats=load_repeats,
        )
        session.add(run)
        await session.commit()
        await session.refresh(run)
        return run


async def get_run(run_id: uuid.UUID) -> Optional[Run]:
    async with get_session() as session:
        return await session.get(Run, run_id)


async def finish_run(run_id: uuid.UUID, termination_reason: str):
    async with get_session() as session:
        run = await session.get(Run, run_id)
        if run:
            run.status = "finished"
            run.termination_reason = termination_reason
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()


async def fail_run(run_id: uuid.UUID, reason: str):
    async with get_session() as session:
        run = await session.get(Run, run_id)
        if run:
            run.status = "failed"
            run.termination_reason = reason
            run.finished_at = datetime.now(timezone.utc)
            await session.commit()


async def save_iteration(
    run_id: uuid.UUID,
    iteration_number: int,
    *,
    config_proposed: Optional[dict] = None,
    config_applied: Optional[dict] = None,
    metrics: Optional[dict] = None,
    judge_analysis: Optional[dict] = None,
    judge_vision_analysis: Optional[dict] = None,
    optimizer_proposal: Optional[dict] = None,
    veto_event: Optional[dict] = None,
    final_decision: Optional[dict] = None,
    baseline_decision: Optional[dict] = None,
) -> Iteration:
    async with get_session() as session:
        iter_obj = Iteration(
            id=uuid.uuid4(),
            run_id=run_id,
            iteration_number=iteration_number,
            config_proposed=config_proposed,
            config_applied=config_applied,
            metrics=metrics,
            judge_analysis=judge_analysis,
            judge_vision_analysis=judge_vision_analysis,
            optimizer_proposal=optimizer_proposal,
            veto_event=veto_event,
            final_decision=final_decision,
            baseline_decision=baseline_decision,
        )
        session.add(iter_obj)
        await session.commit()
        await session.refresh(iter_obj)
        return iter_obj


async def update_iteration(iteration_id: uuid.UUID, **kwargs) -> Optional[Iteration]:
    async with get_session() as session:
        it = await session.get(Iteration, iteration_id)
        if it is None:
            return None
        for k, v in kwargs.items():
            if hasattr(it, k):
                setattr(it, k, v)
        await session.commit()
        await session.refresh(it)
        return it


async def get_iterations(run_id: uuid.UUID) -> list[Iteration]:
    async with get_session() as session:
        result = await session.execute(
            select(Iteration)
            .where(Iteration.run_id == run_id)
            .order_by(Iteration.iteration_number)
        )
        return list(result.scalars().all())


async def list_runs() -> list[Run]:
    async with get_session() as session:
        result = await session.execute(select(Run).order_by(Run.created_at.desc()))
        return list(result.scalars().all())
