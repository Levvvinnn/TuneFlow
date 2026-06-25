import uuid
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode: Mapped[str] = mapped_column(String(50), nullable=False)  # "multi_agent" | "baseline"
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="running")
    target_p95_ms: Mapped[float] = mapped_column(nullable=True)
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    plateau_n: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    vus: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    load_duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    load_repeats: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    # Text, not VARCHAR(100): this column holds both short labels
    # ("max_iterations", "plateau") and full exception messages from a failed
    # agent node (e.g. an httpx "403 Forbidden for url ..." error), which
    # routinely exceed 100 characters and previously crashed fail_run() with
    # a StringDataRightTruncationError, masking the real failure a second time.
    termination_reason: Mapped[str] = mapped_column(Text, nullable=True)


class Iteration(Base):
    __tablename__ = "iterations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    iteration_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Config proposed and applied
    config_proposed: Mapped[dict] = mapped_column(JSONB, nullable=True)
    config_applied: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Raw k6 metrics
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Judge text analysis (structured bottleneck diagnosis from text/JSON input)
    judge_analysis: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Judge vision analysis (from rendered chart image — separate field)
    judge_vision_analysis: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Optimizer's proposed next change
    optimizer_proposal: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Veto event: {vetoed: bool, reason: str, revision_attempt: int, revision_proposal: dict}
    veto_event: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Final decision applied to next iteration
    final_decision: Mapped[dict] = mapped_column(JSONB, nullable=True)

    # Baseline god-agent output (only set in baseline mode)
    baseline_decision: Mapped[dict] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_iterations_run_iter", "run_id", "iteration_number"),
    )
