"""
Tests for multi-objective scoring: weighted metric combination + soft
constraints in termination.score_from_metrics, and describe_objective.
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

from termination import (
    CONSTRAINT_PENALTY,
    DEFAULT_OBJECTIVE_WEIGHTS,
    describe_objective,
    score_from_metrics,
)

METRICS = {
    "p95_latency_ms": 300.0,
    "p99_latency_ms": 450.0,
    "throughput_rps": 80.0,
    "error_rate": 0.01,
}


# ── Backward compatibility ────────────────────────────────────────────────────

def test_default_matches_original_formula():
    """No-arg call must reproduce the original p95 + error_rate*10000 exactly."""
    assert score_from_metrics(METRICS) == 300.0 + 0.01 * 10000  # 400.0


def test_default_no_errors():
    assert score_from_metrics({"p95_latency_ms": 100.0, "error_rate": 0.0}) == 100.0


def test_explicit_default_weights_match_no_arg_call():
    assert score_from_metrics(METRICS, DEFAULT_OBJECTIVE_WEIGHTS) == score_from_metrics(METRICS)


# ── Weighted combinations ─────────────────────────────────────────────────────

def test_p99_weight_included():
    score = score_from_metrics(METRICS, {"p99_latency_ms": 0.5})
    # default p95 (1.0) + err (10000) still applied, plus 0.5 * 450
    assert score == 300.0 + 100.0 + 225.0


def test_throughput_weight_subtracts():
    score = score_from_metrics(METRICS, {"throughput_rps": 2.0})
    assert score == 300.0 + 100.0 - 160.0


def test_partial_override_keeps_other_defaults():
    """Overriding one weight must not zero the others."""
    score = score_from_metrics(METRICS, {"p95_latency_ms": 2.0})
    assert score == 600.0 + 100.0  # err weight still 10000 by default


def test_weights_change_config_ranking():
    """The point of the feature: different objectives rank configs differently."""
    latency_focused = {"p95_latency_ms": 1.0, "error_rate": 10000.0}
    throughput_focused = {"p95_latency_ms": 0.2, "throughput_rps": 5.0, "error_rate": 10000.0}

    config_a = {"p95_latency_ms": 150.0, "throughput_rps": 40.0, "error_rate": 0.0}  # fast, low RPS
    config_b = {"p95_latency_ms": 250.0, "throughput_rps": 120.0, "error_rate": 0.0}  # slower, high RPS

    # Latency objective prefers A
    assert score_from_metrics(config_a, latency_focused) < score_from_metrics(config_b, latency_focused)
    # Throughput objective prefers B
    assert score_from_metrics(config_b, throughput_focused) < score_from_metrics(config_a, throughput_focused)


def test_zero_weight_skips_missing_metric_no_nan():
    """weight=0 on a missing p95 (defaults to inf) must not produce 0*inf=nan."""
    score = score_from_metrics({"error_rate": 0.01}, {"p95_latency_ms": 0.0})
    assert not math.isnan(score)
    assert score == 100.0


def test_missing_p95_with_nonzero_weight_is_inf():
    assert score_from_metrics({"error_rate": 0.0}) == float("inf")


# ── Soft constraints ──────────────────────────────────────────────────────────

def test_min_throughput_constraint_satisfied_no_penalty():
    base = score_from_metrics(METRICS)
    assert score_from_metrics(METRICS, min_throughput_rps=50.0) == base  # 80 >= 50


def test_min_throughput_constraint_violated_penalized():
    base = score_from_metrics(METRICS)
    penalized = score_from_metrics(METRICS, min_throughput_rps=100.0)  # 80 < 100
    assert penalized > base + CONSTRAINT_PENALTY  # at least the base penalty


def test_min_throughput_penalty_proportional():
    slightly = score_from_metrics(METRICS, min_throughput_rps=90.0)   # 11% short
    badly = score_from_metrics(METRICS, min_throughput_rps=200.0)     # 60% short
    assert badly > slightly  # worse violation = worse score (gradient, not cliff)


def test_max_error_rate_constraint_satisfied_no_penalty():
    base = score_from_metrics(METRICS)
    assert score_from_metrics(METRICS, max_error_rate=0.05) == base  # 0.01 <= 0.05


def test_max_error_rate_constraint_violated_penalized():
    base = score_from_metrics(METRICS)
    penalized = score_from_metrics(METRICS, max_error_rate=0.005)  # 0.01 > 0.005
    assert penalized > base + CONSTRAINT_PENALTY


def test_both_constraints_stack():
    one = score_from_metrics(METRICS, min_throughput_rps=100.0)
    both = score_from_metrics(METRICS, min_throughput_rps=100.0, max_error_rate=0.005)
    assert both > one


def test_constraint_violating_config_never_beats_satisfying_one():
    """A config violating the RPS floor should lose to a much slower config that meets it."""
    fast_but_violating = {"p95_latency_ms": 100.0, "throughput_rps": 30.0, "error_rate": 0.0}
    slow_but_ok = {"p95_latency_ms": 600.0, "throughput_rps": 90.0, "error_rate": 0.0}
    kwargs = {"min_throughput_rps": 80.0}
    assert score_from_metrics(slow_but_ok, **kwargs) < score_from_metrics(fast_but_violating, **kwargs)


# ── describe_objective ────────────────────────────────────────────────────────

def test_describe_default():
    desc = describe_objective()
    assert "minimize p95 latency" in desc
    assert "error rate" in desc
    assert "throughput" not in desc  # zero-weight terms omitted


def test_describe_with_throughput_and_constraints():
    desc = describe_objective(
        {"throughput_rps": 2.0},
        min_throughput_rps=100.0,
        max_error_rate=0.01,
    )
    assert "maximize throughput" in desc
    assert "throughput >= 100" in desc
    assert "error rate <= 0.01" in desc
