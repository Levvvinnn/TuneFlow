"""
Tests for Judge Agent veto logic and round-limit enforcement.
Tests run without Fireworks API calls by mocking the optimizer revision function.
"""
import asyncio
import sys
import os
import pytest
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))

from judge_agent import check_safety_constraints, SAFETY_CONSTRAINTS


# ── Safety constraint checks ──────────────────────────────────────────────────

def test_pool_size_below_minimum_vetoed():
    proposal = {"pool_size": 1, "query_timeout_ms": 2000}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is False
    assert "pool_size" in reason


def test_pool_size_at_minimum_passes():
    proposal = {"pool_size": 2, "query_timeout_ms": 2000}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is True
    assert reason == ""


def test_query_timeout_too_aggressive_vetoed():
    proposal = {"pool_size": 5, "query_timeout_ms": 100}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is False
    assert "query_timeout_ms" in reason


def test_query_timeout_at_minimum_passes():
    proposal = {"pool_size": 5, "query_timeout_ms": 500}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is True


def test_retry_interval_too_low_vetoed():
    proposal = {"pool_size": 5, "query_timeout_ms": 2000, "retry_interval_ms": 5}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is False
    assert "retry_interval_ms" in reason


def test_all_valid_passes():
    proposal = {
        "pool_size": 10,
        "query_timeout_ms": 3000,
        "cache_ttl_seconds": 120,
        "batch_size": 200,
        "retry_interval_ms": 50,
    }
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is True
    assert reason == ""


def test_missing_keys_skipped():
    # Only validate keys that are present — missing ones are not vetoed
    proposal = {"pool_size": 5}
    is_safe, reason = check_safety_constraints(proposal)
    assert is_safe is True


# ── Veto round-limit enforcement (unit test of veto_node logic) ───────────────

@pytest.mark.asyncio
async def test_veto_node_one_revision_limit():
    """
    The veto_node must allow exactly ONE revision attempt.
    Simulate: original proposal violates constraint → revision also violates → forced fallback.
    """
    from graph import veto_node, AgentState

    bad_proposal = {
        "pool_size": 1,  # violates minimum (< 2)
        "query_timeout_ms": 3000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100,
    }

    # Revision also violates (to test forced fallback)
    still_bad_revision = {
        "pool_size": 1,  # still violates
        "query_timeout_ms": 3000,
        "cache_ttl_seconds": 60,
        "batch_size": 100,
        "retry_interval_ms": 100,
        "rationale": "revised",
        "change_summary": "none",
        "revision_note": "attempted fix",
    }

    state: AgentState = {
        "run_id": "test-run-id",
        "mode": "multi_agent",
        "iteration_number": 1,
        "max_iterations": 15,
        "plateau_n": 3,
        "target_p95_ms": None,
        "vus": 100,
        "load_duration_seconds": 30,
        "load_repeats": 2,
        "current_config": {"pool_size": 5, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100},
        "proposed_config": None,
        "judge_output": {"metrics": {}, "text_diagnosis": {}},
        "optimizer_proposal": bad_proposal,
        "veto_event": None,
        "final_decision": None,
        "scores": [],
        "iteration_history": [],
        "termination_reason": None,
        "error": None,
        "_save_iteration": None,
    }

    with patch("graph.optimizer.revise_proposal", new_callable=AsyncMock) as mock_revise:
        mock_revise.return_value = still_bad_revision
        result = await veto_node(state)

    veto_event = result["veto_event"]
    assert veto_event["vetoed"] is True
    assert veto_event["revision_attempt"] == 1  # exactly one revision
    assert veto_event["revision_accepted"] is False
    assert veto_event.get("forced_fallback") is True
    # Final decision falls back to current config, not the bad proposal
    assert result["final_decision"] == state["current_config"]
    # revise_proposal was called exactly once — round limit enforced
    mock_revise.assert_called_once()


@pytest.mark.asyncio
async def test_veto_node_revision_accepted():
    """Revision fixes the violation → revision_accepted=True, final_decision = revision."""
    from graph import veto_node, AgentState

    bad_proposal = {"pool_size": 1, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100}
    good_revision = {"pool_size": 8, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100, "rationale": "fixed", "change_summary": "increased pool_size", "revision_note": "respected min"}

    state: AgentState = {
        "run_id": "test-run-id", "mode": "multi_agent", "iteration_number": 1,
        "max_iterations": 15, "plateau_n": 3, "target_p95_ms": None, "vus": 100,
        "load_duration_seconds": 30, "load_repeats": 2,
        "current_config": {"pool_size": 5, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100},
        "proposed_config": None, "judge_output": {"metrics": {}, "text_diagnosis": {}},
        "optimizer_proposal": bad_proposal, "veto_event": None, "final_decision": None,
        "scores": [], "iteration_history": [], "termination_reason": None, "error": None,
        "_save_iteration": None,
    }

    with patch("graph.optimizer.revise_proposal", new_callable=AsyncMock) as mock_revise:
        mock_revise.return_value = good_revision
        result = await veto_node(state)

    veto_event = result["veto_event"]
    assert veto_event["vetoed"] is True
    assert veto_event["revision_attempt"] == 1
    assert veto_event["revision_accepted"] is True
    assert result["final_decision"]["pool_size"] == 8


@pytest.mark.asyncio
async def test_veto_node_no_veto_when_safe():
    """Safe proposal passes through without any revision call."""
    from graph import veto_node, AgentState

    safe_proposal = {"pool_size": 10, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100, "rationale": "good"}

    state: AgentState = {
        "run_id": "test-run-id", "mode": "multi_agent", "iteration_number": 1,
        "max_iterations": 15, "plateau_n": 3, "target_p95_ms": None, "vus": 100,
        "load_duration_seconds": 30, "load_repeats": 2,
        "current_config": {"pool_size": 5, "query_timeout_ms": 3000, "cache_ttl_seconds": 60, "batch_size": 100, "retry_interval_ms": 100},
        "proposed_config": None, "judge_output": {}, "optimizer_proposal": safe_proposal,
        "veto_event": None, "final_decision": None, "scores": [], "iteration_history": [],
        "termination_reason": None, "error": None, "_save_iteration": None,
    }

    with patch("graph.optimizer.revise_proposal", new_callable=AsyncMock) as mock_revise:
        result = await veto_node(state)

    assert result["veto_event"]["vetoed"] is False
    assert result["final_decision"] == safe_proposal
    mock_revise.assert_not_called()
