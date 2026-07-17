"""
Tests for disagreement-based abstention (DBA, arXiv:2602.04853):
cross-regime diagnosis agreement checks and the veto_node abstention path.
No Fireworks API calls — everything is checked against dicts or mocked.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

from judge_agent import check_diagnosis_agreement, dba_enabled, dba_shadow_mode


# ── check_diagnosis_agreement ─────────────────────────────────────────────────

def test_same_bottleneck_agrees():
    agree, reason = check_diagnosis_agreement(
        {"bottleneck": "pool_exhaustion"},
        {"bottleneck": "pool_exhaustion"},
    )
    assert agree is True
    assert "agree" in reason


def test_different_bottleneck_disagrees():
    agree, reason = check_diagnosis_agreement(
        {"bottleneck": "cache_miss"},
        {"bottleneck": "pool_exhaustion"},
    )
    assert agree is False
    assert "cache_miss" in reason
    assert "pool_exhaustion" in reason


def test_unknown_direct_is_not_comparable():
    # "unknown" is absence of an answer, not a conflicting answer — no abstention
    agree, _ = check_diagnosis_agreement(
        {"bottleneck": "unknown"},
        {"bottleneck": "pool_exhaustion"},
    )
    assert agree is True


def test_unknown_decomposed_is_not_comparable():
    agree, _ = check_diagnosis_agreement(
        {"bottleneck": "slow_queries"},
        {"bottleneck": "unknown"},
    )
    assert agree is True


def test_missing_diagnosis_is_not_comparable():
    assert check_diagnosis_agreement(None, {"bottleneck": "cache_miss"})[0] is True
    assert check_diagnosis_agreement({"bottleneck": "cache_miss"}, None)[0] is True
    assert check_diagnosis_agreement({}, {})[0] is True


# ── dba_enabled toggle ────────────────────────────────────────────────────────

def test_dba_enabled_by_default(monkeypatch):
    monkeypatch.delenv("DBA_ABSTENTION", raising=False)
    assert dba_enabled() is True


def test_dba_disabled_via_env(monkeypatch):
    monkeypatch.setenv("DBA_ABSTENTION", "false")
    assert dba_enabled() is False


def test_dba_enabled_via_env_variants(monkeypatch):
    for val in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("DBA_ABSTENTION", val)
        assert dba_enabled() is True, f"expected enabled for {val!r}"


# ── veto_node abstention path ─────────────────────────────────────────────────

def _base_state(judge_output, proposal):
    return {
        "run_id": "test-run-id",
        "mode": "multi_agent",
        "iteration_number": 2,
        "max_iterations": 15,
        "plateau_n": 3,
        "target_p95_ms": None,
        "vus": 100,
        "load_duration_seconds": 30,
        "load_repeats": 2,
        "current_config": {
            "pool_size": 10, "query_timeout_ms": 3000, "cache_ttl_seconds": 60,
            "batch_size": 100, "retry_interval_ms": 100,
        },
        "proposed_config": None,
        "judge_output": judge_output,
        "optimizer_proposal": proposal,
        "veto_event": None,
        "final_decision": None,
        "scores": [400.0],
        "iteration_history": [],
        "termination_reason": None,
        "error": None,
        "_save_iteration": None,
    }


SAFE_PROPOSAL = {
    "pool_size": 15, "query_timeout_ms": 3000, "cache_ttl_seconds": 120,
    "batch_size": 100, "retry_interval_ms": 100, "rationale": "test",
}


@pytest.mark.asyncio
async def test_veto_node_abstains_on_disagreement(monkeypatch):
    """Direct and decomposed diagnoses conflict → abstain, keep current config."""
    monkeypatch.setenv("DBA_ABSTENTION", "true")
    from graph import veto_node

    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "cache_miss"},
    }
    state = _base_state(judge_output, SAFE_PROPOSAL)

    result = await veto_node(state)

    veto_event = result["veto_event"]
    assert veto_event["vetoed"] is True
    assert veto_event["veto_type"] == "disagreement_abstention"
    assert veto_event["abstained"] is True
    assert veto_event["direct_bottleneck"] == "cache_miss"
    assert veto_event["decomposed_bottleneck"] == "pool_exhaustion"
    # Abstained → proposal discarded, current config kept
    assert result["final_decision"] == state["current_config"]


@pytest.mark.asyncio
async def test_veto_node_no_abstention_on_agreement(monkeypatch):
    """Diagnoses agree → normal safety-check path, safe proposal accepted."""
    monkeypatch.setenv("DBA_ABSTENTION", "true")
    from graph import veto_node

    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "pool_exhaustion"},
    }
    state = _base_state(judge_output, SAFE_PROPOSAL)

    result = await veto_node(state)

    assert result["veto_event"]["vetoed"] is False
    assert result["final_decision"] == SAFE_PROPOSAL


@pytest.mark.asyncio
async def test_veto_node_skips_dba_when_disabled(monkeypatch):
    """DBA disabled → disagreement is ignored, safety check runs as before."""
    monkeypatch.setenv("DBA_ABSTENTION", "false")
    from graph import veto_node

    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "cache_miss"},  # disagrees, but DBA off
    }
    state = _base_state(judge_output, SAFE_PROPOSAL)

    result = await veto_node(state)

    assert result["veto_event"]["vetoed"] is False
    assert result["final_decision"] == SAFE_PROPOSAL


@pytest.mark.asyncio
async def test_veto_node_no_abstention_when_direct_unknown(monkeypatch):
    """Direct diagnosis 'unknown' → not comparable, no abstention."""
    monkeypatch.setenv("DBA_ABSTENTION", "true")
    from graph import veto_node

    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "unknown"},
    }
    state = _base_state(judge_output, SAFE_PROPOSAL)

    result = await veto_node(state)

    assert result["veto_event"]["vetoed"] is False
    assert result["final_decision"] == SAFE_PROPOSAL


@pytest.mark.asyncio
async def test_veto_node_shadow_mode_records_but_does_not_abstain(monkeypatch):
    """
    DBA_SHADOW_MODE=true: disagreement is recorded on veto_event (with
    would_abstain=True) but the proposal still goes through — needed so
    scripts/analyze_dba_outcomes.py can measure what would have happened.
    """
    monkeypatch.setenv("DBA_ABSTENTION", "true")
    monkeypatch.setenv("DBA_SHADOW_MODE", "true")
    from graph import veto_node

    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "cache_miss"},
    }
    state = _base_state(judge_output, SAFE_PROPOSAL)

    result = await veto_node(state)

    veto_event = result["veto_event"]
    # Not abstained — proposal applied despite the disagreement
    assert veto_event["vetoed"] is False
    assert veto_event["would_abstain"] is True
    assert veto_event["dba"]["agrees"] is False
    assert veto_event["dba"]["direct_bottleneck"] == "cache_miss"
    assert veto_event["dba"]["decomposed_bottleneck"] == "pool_exhaustion"
    assert result["final_decision"] == SAFE_PROPOSAL


def test_dba_shadow_mode_disabled_by_default(monkeypatch):
    monkeypatch.delenv("DBA_SHADOW_MODE", raising=False)
    assert dba_shadow_mode() is False


def test_dba_shadow_mode_enabled_via_env(monkeypatch):
    monkeypatch.setenv("DBA_SHADOW_MODE", "true")
    assert dba_shadow_mode() is True


@pytest.mark.asyncio
async def test_abstention_takes_precedence_over_safety_veto(monkeypatch):
    """Disagreement fires before the safety check — proposal never gets a revision."""
    monkeypatch.setenv("DBA_ABSTENTION", "true")
    from graph import veto_node

    unsafe_proposal = {
        "pool_size": 1,  # violates safety minimum
        "query_timeout_ms": 3000, "cache_ttl_seconds": 60,
        "batch_size": 100, "retry_interval_ms": 100,
    }
    judge_output = {
        "metrics": {},
        "text_diagnosis": {"bottleneck": "pool_exhaustion"},
        "direct_diagnosis": {"bottleneck": "slow_queries"},
    }
    state = _base_state(judge_output, unsafe_proposal)

    result = await veto_node(state)

    veto_event = result["veto_event"]
    assert veto_event["veto_type"] == "disagreement_abstention"
    assert veto_event["revision_attempt"] == 0  # no revision round consumed
    assert result["final_decision"] == state["current_config"]
