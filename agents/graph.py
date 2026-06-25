"""
LangGraph multi-agent graph for the TuneFlow tuning loop.

Graph nodes:
  config_node      → proposes next config (Config Agent)
  judge_node       → applies config, runs load test, diagnoses (Judge Agent)
  optimizer_node   → proposes next change (Optimizer Agent)
  veto_node        → checks safety constraints, handles 1-revision round
  terminate_node   → checks termination conditions (target/plateau/max)

State flows: config_node → judge_node → optimizer_node → veto_node → terminate_node
             └─ if not terminated → config_node (next iteration)
"""
import asyncio
import os
import sys
import uuid
from typing import Annotated, Any, Optional, TypedDict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "persistence"))

from langgraph.graph import END, StateGraph

import config_agent as cfg_agent
import judge_agent as judge
import optimizer_agent as optimizer
from termination import check_termination, score_from_metrics

# ── State schema ──────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    run_id: str
    mode: str  # "multi_agent"
    iteration_number: int
    max_iterations: int
    plateau_n: int
    target_p95_ms: Optional[float]
    vus: int
    load_duration_seconds: int
    load_repeats: int

    current_config: dict
    proposed_config: Optional[dict]
    judge_output: Optional[dict]
    optimizer_proposal: Optional[dict]
    veto_event: Optional[dict]
    final_decision: Optional[dict]

    scores: list[float]
    iteration_history: list[dict]

    termination_reason: Optional[str]
    error: Optional[str]

    # Persistence callbacks (injected at runtime — not serialized)
    _save_iteration: Optional[Any]
    _update_iteration: Optional[Any]


# ── Node implementations ──────────────────────────────────────────────────────

async def config_node(state: AgentState) -> dict:
    """Propose next config (initial or targeted change)."""
    iteration = state["iteration_number"]
    try:
        if iteration == 1:
            proposed = await cfg_agent.propose_initial_config()
        else:
            proposed = await cfg_agent.propose_config_change(
                current_config=state["current_config"],
                judge_analysis=state.get("judge_output", {}).get("text_diagnosis", {}),
                iteration_history=state["iteration_history"],
            )
        return {"proposed_config": proposed, "error": None}
    except Exception as e:
        print(f"[config_node] ERROR: {e}", flush=True)
        return {"error": f"Config Agent failed: {e}"}


async def judge_node(state: AgentState) -> dict:
    """Apply config, run load test, diagnose."""
    proposed = state.get("proposed_config") or state["current_config"]
    try:
        output = await judge.full_judge_cycle(
            proposed_config=proposed,
            iteration_history=state["iteration_history"],
            vus=state["vus"],
            duration_seconds=state["load_duration_seconds"],
            repeats=state["load_repeats"],
        )
        return {
            "judge_output": output,
            "current_config": proposed,
            "error": None,
        }
    except Exception as e:
        print(f"[judge_node] ERROR: {e}", flush=True)
        return {"error": f"Judge Agent failed: {e}"}


async def optimizer_node(state: AgentState) -> dict:
    """Propose next config change from Judge analysis."""
    judge_out = state.get("judge_output", {})
    try:
        proposal = await optimizer.propose_next_config(
            current_config=state["current_config"],
            judge_output=judge_out,
            iteration_history=state["iteration_history"],
        )
        return {"optimizer_proposal": proposal, "error": None}
    except Exception as e:
        print(f"[optimizer_node] ERROR: {e}", flush=True)
        return {"error": f"Optimizer Agent failed: {e}"}


async def veto_node(state: AgentState) -> dict:
    """
    Check optimizer proposal against safety constraints.
    If vetoed, allow exactly ONE revision attempt.
    Enforces the round limit in code — a stuck negotiation cannot eat the iteration budget.
    """
    proposal = state.get("optimizer_proposal", {})
    judge_out = state.get("judge_output", {})

    is_safe, reason = judge.check_safety_constraints(proposal)
    veto_event: dict = {
        "vetoed": not is_safe,
        "reason": reason,
        "revision_attempt": 0,
        "original_proposal": {k: v for k, v in proposal.items() if k in cfg_agent.PARAM_BOUNDS},
    }

    if is_safe:
        return {
            "final_decision": proposal,
            "veto_event": veto_event,
            "optimizer_proposal": proposal,
            "error": None,
        }

    # Veto — request one revision
    try:
        revised = await optimizer.revise_proposal(
            original_proposal=proposal,
            veto_reason=reason,
            current_config=state["current_config"],
            judge_output=judge_out,
            iteration_history=state["iteration_history"],
        )
        veto_event["revision_attempt"] = 1
        veto_event["revision_proposal"] = {k: v for k, v in revised.items() if k in cfg_agent.PARAM_BOUNDS}

        # Check revised proposal
        revised_safe, revised_reason = judge.check_safety_constraints(revised)
        veto_event["revision_accepted"] = revised_safe
        veto_event["revision_veto_reason"] = revised_reason if not revised_safe else None

        # Whether revision passed or not, this is the final answer for this iteration
        # (round limit = 1 revision, enforced here)
        final = revised if revised_safe else state["current_config"]
        if not revised_safe:
            veto_event["forced_fallback"] = True

        return {
            "final_decision": final,
            "veto_event": veto_event,
            "error": None,
        }
    except Exception as e:
        # If revision call fails, fall back to current config
        veto_event["revision_attempt"] = 1
        veto_event["revision_error"] = str(e)
        veto_event["forced_fallback"] = True
        return {
            "final_decision": state["current_config"],
            "veto_event": veto_event,
            "error": None,
        }


async def persist_node(state: AgentState) -> dict:
    """Save iteration data to persistence DB, update history."""
    judge_out = state.get("judge_output", {})
    metrics = judge_out.get("metrics", {})

    iteration_entry = {
        "iteration_number": state["iteration_number"],
        "p95_latency_ms": metrics.get("p95_latency_ms", 0),
        "p99_latency_ms": metrics.get("p99_latency_ms", 0),
        "throughput_rps": metrics.get("throughput_rps", 0),
        "error_rate": metrics.get("error_rate", 0),
        "config_applied": state.get("current_config", {}),
    }

    new_history = state["iteration_history"] + [iteration_entry]
    new_scores = state["scores"] + [score_from_metrics(metrics)]

    save_fn = state.get("_save_iteration")
    if save_fn:
        try:
            await save_fn(
                run_id=uuid.UUID(state["run_id"]),
                iteration_number=state["iteration_number"],
                config_proposed=state.get("proposed_config"),
                config_applied=state.get("current_config"),
                metrics=metrics,
                judge_analysis=judge_out.get("text_diagnosis"),
                judge_vision_analysis=judge_out.get("vision_diagnosis"),
                optimizer_proposal=state.get("optimizer_proposal"),
                veto_event=state.get("veto_event"),
                final_decision=state.get("final_decision"),
            )
        except Exception as e:
            pass  # Persistence failure is non-fatal to the loop

    return {
        "iteration_history": new_history,
        "scores": new_scores,
    }


async def terminate_node(state: AgentState) -> dict:
    """Check all three termination conditions."""
    result = check_termination(
        iteration_number=state["iteration_number"],
        scores=state["scores"],
        max_iterations=state["max_iterations"],
        plateau_n=state["plateau_n"],
        target_score=state["target_p95_ms"],  # using p95 target as score target
    )
    if result.should_stop:
        return {
            "termination_reason": result.reason,
            "iteration_number": state["iteration_number"],
        }
    return {
        "termination_reason": None,
        "iteration_number": state["iteration_number"] + 1,
        # Carry final_decision as proposed_config for next iteration
        "proposed_config": state.get("final_decision"),
    }


# ── Routing ───────────────────────────────────────────────────────────────────

def should_terminate(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    if state.get("termination_reason"):
        return END
    return "config"


def route_after_judge(state: AgentState) -> str:
    if state.get("error"):
        return "error"
    return "optimizer"


# ── Graph assembly ────────────────────────────────────────────────────────────

def build_graph():
    g = StateGraph(AgentState)

    g.add_node("config", config_node)
    g.add_node("judge", judge_node)
    g.add_node("optimizer", optimizer_node)
    g.add_node("veto", veto_node)
    g.add_node("persist", persist_node)
    g.add_node("terminate", terminate_node)

    g.set_entry_point("config")
    g.add_edge("config", "judge")
    g.add_conditional_edges("judge", route_after_judge, {"optimizer": "optimizer", "error": END})
    g.add_edge("optimizer", "veto")
    g.add_edge("veto", "persist")
    g.add_edge("persist", "terminate")
    g.add_conditional_edges(
        "terminate",
        should_terminate,
        {"config": "config", END: END, "error": END},
    )

    return g.compile()


MULTI_AGENT_GRAPH = build_graph()


async def run_multi_agent(
    run_id: str,
    max_iterations: int = 15,
    plateau_n: int = 3,
    target_p95_ms: Optional[float] = None,
    vus: int = 100,
    load_duration_seconds: int = 30,
    load_repeats: int = 2,
    save_iteration_fn=None,
) -> dict:
    """Entry point for a full multi-agent tuning run."""
    initial_state: AgentState = {
        "run_id": run_id,
        "mode": "multi_agent",
        "iteration_number": 1,
        "max_iterations": max_iterations,
        "plateau_n": plateau_n,
        "target_p95_ms": target_p95_ms,
        "vus": vus,
        "load_duration_seconds": load_duration_seconds,
        "load_repeats": load_repeats,
        "current_config": cfg_agent.DEFAULT_CONFIG.copy(),
        "proposed_config": None,
        "judge_output": None,
        "optimizer_proposal": None,
        "veto_event": None,
        "final_decision": None,
        "scores": [],
        "iteration_history": [],
        "termination_reason": None,
        "error": None,
        "_save_iteration": save_iteration_fn,
        "_update_iteration": None,
    }
    final_state = await MULTI_AGENT_GRAPH.ainvoke(initial_state)
    return final_state
