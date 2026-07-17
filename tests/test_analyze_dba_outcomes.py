"""
Tests for scripts/analyze_dba_outcomes.py — the bucketing and scoring logic
used to evaluate whether DBA disagreement actually correlates with worse
tuning outcomes. Uses synthetic iteration data, no live run required.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from analyze_dba_outcomes import (
    build_outcome_rows,
    classify_iteration,
    score_from_metrics,
    summarize,
)


def _iter(number, p95, err_rate=0.0, veto_event=None):
    return {
        "iteration_number": number,
        "metrics": {"p95_latency_ms": p95, "error_rate": err_rate},
        "veto_event": veto_event,
    }


# ── score_from_metrics ────────────────────────────────────────────────────────

def test_score_from_metrics_matches_termination_scoring():
    assert score_from_metrics({"p95_latency_ms": 200.0, "error_rate": 0.01}) == 200.0 + 0.01 * 10000
    assert score_from_metrics({"p95_latency_ms": 100.0, "error_rate": 0.0}) == 100.0


# ── classify_iteration ────────────────────────────────────────────────────────

def test_classify_agree():
    veto_event = {"vetoed": False, "dba": {"agrees": True, "direct_bottleneck": "pool_exhaustion", "decomposed_bottleneck": "pool_exhaustion"}}
    bucket, direct_b, decomposed_b = classify_iteration(_iter(1, 300, veto_event=veto_event))
    assert bucket == "agree"
    assert direct_b == decomposed_b == "pool_exhaustion"


def test_classify_disagree_shadow():
    veto_event = {"vetoed": False, "dba": {"agrees": False, "direct_bottleneck": "cache_miss", "decomposed_bottleneck": "pool_exhaustion"}, "would_abstain": True}
    bucket, direct_b, decomposed_b = classify_iteration(_iter(1, 300, veto_event=veto_event))
    assert bucket == "disagree_shadow"
    assert direct_b == "cache_miss"
    assert decomposed_b == "pool_exhaustion"


def test_classify_disagree_abstained():
    veto_event = {
        "vetoed": True,
        "veto_type": "disagreement_abstention",
        "abstained": True,
        "direct_bottleneck": "cache_miss",
        "decomposed_bottleneck": "pool_exhaustion",
    }
    bucket, direct_b, decomposed_b = classify_iteration(_iter(1, 300, veto_event=veto_event))
    assert bucket == "disagree_abstained"
    assert direct_b == "cache_miss"


def test_classify_no_dba_data():
    veto_event = {"vetoed": False}
    bucket, _, _ = classify_iteration(_iter(1, 300, veto_event=veto_event))
    assert bucket == "no_dba_data"


def test_classify_missing_veto_event():
    bucket, _, _ = classify_iteration({"iteration_number": 1, "metrics": {"p95_latency_ms": 300}})
    assert bucket == "no_dba_data"


# ── build_outcome_rows ────────────────────────────────────────────────────────

def test_build_outcome_rows_computes_improvement():
    iterations = [
        _iter(1, 500, veto_event={"vetoed": False, "dba": {"agrees": True}}),
        _iter(2, 300, veto_event={"vetoed": False, "dba": {"agrees": True}}),  # improved
        _iter(3, 350, veto_event={"vetoed": False, "dba": {"agrees": False}, "would_abstain": True}),  # regressed
    ]
    rows = build_outcome_rows("run-1", iterations)

    assert len(rows) == 3
    assert rows[0].bucket == "agree"
    assert rows[0].improved is True
    assert rows[0].score_delta == 200.0  # 500 - 300

    assert rows[1].bucket == "agree"
    assert rows[1].improved is False  # 300 -> 350 got worse
    assert rows[1].score_delta == -50.0

    # Last iteration has no following iteration → no outcome
    assert rows[2].improved is None
    assert rows[2].score_after is None


def test_build_outcome_rows_skips_iterations_without_metrics():
    iterations = [
        _iter(1, 500),
        {"iteration_number": 2, "metrics": None},
        _iter(3, 300),
    ]
    rows = build_outcome_rows("run-1", iterations)
    assert len(rows) == 2  # the metrics-less iteration is skipped
    assert [r.iteration_number for r in rows] == [1, 3]


def test_build_outcome_rows_sorts_by_iteration_number():
    iterations = [_iter(2, 300), _iter(1, 500)]
    rows = build_outcome_rows("run-1", iterations)
    assert [r.iteration_number for r in rows] == [1, 2]
    assert rows[0].improved is True  # 500 -> 300


# ── summarize ──────────────────────────────────────────────────────────────────

def test_summarize_computes_bucket_stats():
    iterations = [
        _iter(1, 500, veto_event={"vetoed": False, "dba": {"agrees": True}}),
        _iter(2, 400, veto_event={"vetoed": False, "dba": {"agrees": True}}),  # agree, improves to iter3: +100
        _iter(3, 380, veto_event={"vetoed": False, "dba": {"agrees": True}}),  # agree, but iter3->iter4 regresses: -10
        _iter(4, 390, veto_event={"vetoed": False, "dba": {"agrees": False}, "would_abstain": True}),  # disagree-shadow, regresses to iter5: -110
        _iter(5, 500, veto_event={"vetoed": False, "dba": {"agrees": False}, "would_abstain": True}),  # disagree-shadow, improves to iter6: +20
        _iter(6, 480),  # terminal, no outcome
    ]
    rows = build_outcome_rows("run-1", iterations)
    summary = summarize(rows)

    # Bucket membership is by each iteration's OWN dba flag, not by whether its
    # own outcome happened to improve — iter1,2,3 are all "agree" iterations
    # even though iter3's own outcome (iter3->iter4) was a regression.
    assert summary["agree"]["n"] == 3
    assert summary["agree"]["improved_rate"] == 2 / 3  # iter1, iter2 improved; iter3 regressed

    assert summary["disagree_shadow"]["n"] == 2
    assert summary["disagree_shadow"]["improved_rate"] == 0.5  # iter4 regressed, iter5 improved
    # (390-500) = -110, (500-480) = +20 → mean = -45
    assert summary["disagree_shadow"]["mean_score_delta"] == -45.0


def test_summarize_empty_bucket_reports_zero():
    rows = build_outcome_rows("run-1", [_iter(1, 500)])  # only 1 iter, no dba data, no outcome
    summary = summarize(rows)
    assert summary["agree"]["n"] == 0
    assert summary["disagree_shadow"]["n"] == 0


def test_summarize_disagree_worse_than_agree_end_to_end():
    """Synthetic scenario where disagreement really does predict worse outcomes —
    sanity-checks that the bucketing correctly surfaces a real effect when present."""
    iterations = []
    # 5 agreement iterations that consistently improve
    for i, p95 in enumerate([500, 450, 400, 370, 350], start=1):
        iterations.append(_iter(i, p95, veto_event={"vetoed": False, "dba": {"agrees": True}}))
    # 5 disagreement iterations that consistently regress or stay flat
    for i, p95 in enumerate([350, 360, 355, 365, 360], start=6):
        iterations.append(_iter(i, p95, veto_event={"vetoed": False, "dba": {"agrees": False}, "would_abstain": True}))
    iterations.append(_iter(11, 358))  # terminal

    rows = build_outcome_rows("run-1", iterations)
    summary = summarize(rows)

    assert summary["agree"]["improved_rate"] > summary["disagree_shadow"]["improved_rate"]
    assert summary["agree"]["mean_score_delta"] > summary["disagree_shadow"]["mean_score_delta"]
