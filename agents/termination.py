"""
Shared termination module — used identically by multi-agent and baseline loops.
Implements: target-hit / plateau-N / max-iterations.
"""
from dataclasses import dataclass
from typing import Optional

# Plateau is judged "no meaningful improvement" if the gain is smaller than
# both of these — a relative fraction of the window's starting score, and a
# small absolute floor for when scores themselves are small.
MIN_RELATIVE_IMPROVEMENT = 0.01  # 1% of the window's starting score
MIN_ABSOLUTE_IMPROVEMENT = 2.0  # floor, in score units (ms-equivalent)


@dataclass
class TerminationResult:
    should_stop: bool
    reason: str  # "target_hit" | "plateau" | "max_iterations" | None


def check_termination(
    iteration_number: int,
    scores: list[float],  # composite scores per iteration (lower is better), most recent last
    max_iterations: int,
    plateau_n: int,
    target_score: Optional[float] = None,  # None = no target
) -> TerminationResult:
    """
    Call after each iteration completes.

    Args:
        iteration_number: 1-based index of the just-completed iteration
        scores: all scores so far (index 0 = iteration 1)
        max_iterations: hard cap on total iterations
        plateau_n: stop if the last N iterations show no improvement
        target_score: stop if the latest score is <= this value
    """
    current_score = scores[-1] if scores else float("inf")

    # 1. Target hit
    if target_score is not None and current_score <= target_score:
        return TerminationResult(should_stop=True, reason="target_hit")

    # 2. Max iterations
    if iteration_number >= max_iterations:
        return TerminationResult(should_stop=True, reason="max_iterations")

    # 3. Plateau detection
    #
    # Scores here are p95 latencies in the hundreds-of-ms range, and repeated load
    # test runs naturally jitter by several ms even with identical config. A fixed
    # absolute tolerance (e.g. 1e-3 ms) is far tighter than that noise floor, so it
    # would almost never fire on real data — the loop would just run to
    # max_iterations every time and the time-budget benefit of plateau detection
    # would be lost. Instead, treat the window as plateaued if the improvement is
    # smaller than both a relative fraction of the window's starting score and a
    # small absolute floor (the floor matters when scores are themselves small).
    if len(scores) >= plateau_n:
        window = scores[-plateau_n:]
        best_in_window = min(window)
        # Plateau: no score in the window improved meaningfully over the oldest in the window
        oldest_in_window = window[0]
        improvement = oldest_in_window - best_in_window  # positive = got better
        threshold = max(MIN_ABSOLUTE_IMPROVEMENT, oldest_in_window * MIN_RELATIVE_IMPROVEMENT)
        if improvement < threshold:
            return TerminationResult(should_stop=True, reason="plateau")

    return TerminationResult(should_stop=False, reason="")


def score_from_metrics(metrics: dict) -> float:
    """Convert a metrics dict to a single scalar score (lower is better)."""
    p95 = metrics.get("p95_latency_ms", float("inf"))
    err_rate = metrics.get("error_rate", 0.0)
    return p95 + err_rate * 10000
