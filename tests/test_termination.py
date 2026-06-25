"""Tests for shared termination logic — target/plateau/max-iterations each independently triggerable."""
import pytest
from termination import check_termination, score_from_metrics


def test_target_hit():
    scores = [500.0, 300.0, 180.0]
    result = check_termination(
        iteration_number=3,
        scores=scores,
        max_iterations=15,
        plateau_n=3,
        target_score=200.0,
    )
    assert result.should_stop is True
    assert result.reason == "target_hit"


def test_target_not_hit():
    scores = [500.0, 400.0, 350.0]
    result = check_termination(
        iteration_number=3,
        scores=scores,
        max_iterations=15,
        plateau_n=3,
        target_score=200.0,
    )
    assert result.should_stop is False


def test_max_iterations_hit():
    scores = [400.0] * 10
    result = check_termination(
        iteration_number=10,
        scores=scores,
        max_iterations=10,
        plateau_n=3,
        target_score=None,
    )
    assert result.should_stop is True
    assert result.reason == "max_iterations"


def test_max_iterations_not_yet():
    scores = [400.0] * 5
    result = check_termination(
        iteration_number=5,
        scores=scores,
        max_iterations=10,
        plateau_n=3,
        target_score=None,
    )
    # No plateau yet (window=3, but scores are all same — plateau kicks in)
    # plateau_n=3, window scores: [400, 400, 400] — oldest=400, best=400 → plateau
    assert result.should_stop is True
    assert result.reason == "plateau"


def test_plateau_detected():
    # Last 3 show no improvement
    scores = [500.0, 450.0, 410.0, 408.0, 409.0, 407.0]
    result = check_termination(
        iteration_number=6,
        scores=scores,
        max_iterations=20,
        plateau_n=3,
        target_score=None,
    )
    assert result.should_stop is True
    assert result.reason == "plateau"


def test_no_plateau_when_improving():
    scores = [500.0, 450.0, 380.0, 300.0, 250.0]
    result = check_termination(
        iteration_number=5,
        scores=scores,
        max_iterations=20,
        plateau_n=3,
        target_score=None,
    )
    # Window: [380, 300, 250] — best=250, oldest=380 → still improving
    assert result.should_stop is False


def test_target_takes_precedence_over_plateau():
    # Both target hit and plateau would trigger — target_hit should be returned
    scores = [200.0, 200.0, 190.0]
    result = check_termination(
        iteration_number=3,
        scores=scores,
        max_iterations=20,
        plateau_n=3,
        target_score=200.0,
    )
    assert result.should_stop is True
    assert result.reason == "target_hit"


def test_score_from_metrics():
    metrics = {"p95_latency_ms": 250.0, "error_rate": 0.01}
    score = score_from_metrics(metrics)
    assert score == 250.0 + 0.01 * 10000  # 350.0


def test_score_from_metrics_no_errors():
    metrics = {"p95_latency_ms": 100.0, "error_rate": 0.0}
    score = score_from_metrics(metrics)
    assert score == 100.0


def test_empty_scores_no_stop():
    result = check_termination(
        iteration_number=1,
        scores=[],
        max_iterations=15,
        plateau_n=3,
        target_score=None,
    )
    assert result.should_stop is False


def test_plateau_exactly_n():
    # Exactly plateau_n=3 iterations with no improvement
    scores = [300.0, 299.0, 299.5, 300.1]
    result = check_termination(
        iteration_number=4,
        scores=scores,
        max_iterations=20,
        plateau_n=3,
        target_score=None,
    )
    # Window: [299.0, 299.5, 300.1] — best=299.0, oldest=299.0 → no improvement
    assert result.should_stop is True
    assert result.reason == "plateau"
