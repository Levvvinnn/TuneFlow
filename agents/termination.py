"""
Shared termination + scoring module — used identically by multi-agent and
baseline loops. Implements: target-hit / plateau-N / max-iterations, and the
configurable multi-objective score that drives all three.
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


# ── Multi-objective scoring ──────────────────────────────────────────────────
#
# The score is a weighted combination of the four metrics the load test
# already collects. Latency and error terms ADD to the score (lower metric =
# better), throughput SUBTRACTS (higher metric = better). The defaults
# reproduce the original single-objective behavior exactly:
# score = p95 + error_rate * 10000.

DEFAULT_OBJECTIVE_WEIGHTS = {
    "p95_latency_ms": 1.0,
    "p99_latency_ms": 0.0,
    "error_rate": 10000.0,
    "throughput_rps": 0.0,
}

# Soft-constraint penalty: a violated constraint adds this much, plus the same
# amount again scaled by how badly it's violated. Large enough that a
# constraint-violating config can essentially never look better than a
# constraint-respecting one at realistic latencies, but still smooth — a config
# that violates by 2x is scored worse than one violating by 10%, so the
# optimizer gets a gradient back toward feasibility instead of a cliff.
CONSTRAINT_PENALTY = 1000.0


def score_from_metrics(
    metrics: dict,
    objective_weights: Optional[dict] = None,
    min_throughput_rps: Optional[float] = None,
    max_error_rate: Optional[float] = None,
) -> float:
    """
    Convert a metrics dict to a single scalar score (lower is better).

    objective_weights: partial override of DEFAULT_OBJECTIVE_WEIGHTS, e.g.
        {"p95_latency_ms": 1.0, "p99_latency_ms": 0.5} to also penalize tail
        latency, or {"throughput_rps": 2.0} to reward throughput.
    min_throughput_rps / max_error_rate: soft constraints — violations add a
        large penalty proportional to how badly they're violated.

    With no arguments this is exactly the original: p95 + error_rate * 10000.
    """
    weights = {**DEFAULT_OBJECTIVE_WEIGHTS, **(objective_weights or {})}

    score = 0.0
    # Additive terms (lower metric = better). Skip zero-weight terms entirely
    # so a missing metric defaulting to inf can't produce 0*inf = nan.
    for key, default in (("p95_latency_ms", float("inf")), ("p99_latency_ms", 0.0), ("error_rate", 0.0)):
        w = weights.get(key, 0.0)
        if w:
            score += w * metrics.get(key, default)
    # Subtractive term (higher metric = better)
    w_rps = weights.get("throughput_rps", 0.0)
    if w_rps:
        score -= w_rps * metrics.get("throughput_rps", 0.0)

    # Soft constraints
    rps = metrics.get("throughput_rps", 0.0)
    err = metrics.get("error_rate", 0.0)
    if min_throughput_rps is not None and min_throughput_rps > 0 and rps < min_throughput_rps:
        shortfall = (min_throughput_rps - rps) / min_throughput_rps
        score += CONSTRAINT_PENALTY * (1.0 + shortfall)
    if max_error_rate is not None and err > max_error_rate:
        excess = (err - max_error_rate) / max(max_error_rate, 1e-9)
        score += CONSTRAINT_PENALTY * (1.0 + min(excess, 10.0))  # cap runaway excess

    return score


def describe_objective(
    objective_weights: Optional[dict] = None,
    min_throughput_rps: Optional[float] = None,
    max_error_rate: Optional[float] = None,
) -> str:
    """Human/LLM-readable one-line description of the active objective, used in
    agent prompts so the Optimizer knows what it is actually optimizing."""
    weights = {**DEFAULT_OBJECTIVE_WEIGHTS, **(objective_weights or {})}
    parts = []
    if weights.get("p95_latency_ms"):
        parts.append(f"minimize p95 latency (weight {weights['p95_latency_ms']:g})")
    if weights.get("p99_latency_ms"):
        parts.append(f"minimize p99 latency (weight {weights['p99_latency_ms']:g})")
    if weights.get("error_rate"):
        parts.append(f"minimize error rate (weight {weights['error_rate']:g})")
    if weights.get("throughput_rps"):
        parts.append(f"maximize throughput (weight {weights['throughput_rps']:g})")
    desc = ", ".join(parts) if parts else "minimize p95 latency"
    constraints = []
    if min_throughput_rps is not None:
        constraints.append(f"keep throughput >= {min_throughput_rps:g} req/s")
    if max_error_rate is not None:
        constraints.append(f"keep error rate <= {max_error_rate:g}")
    if constraints:
        desc += "; hard preferences: " + " and ".join(constraints)
    return desc
