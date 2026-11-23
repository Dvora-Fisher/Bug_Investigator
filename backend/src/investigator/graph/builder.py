"""Assembles the investigation graph: 11 nodes, fixed edges for the intake, conditional edges after that."""

from __future__ import annotations

import logging
from functools import wraps

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from ..budget import BudgetExceeded
from ..config import InvestigationMode, Settings
from ..llm import ReasoningFailed
from ..sandbox.workspace import WorkspaceError
from .context import InvestigationContext, Rt
from .nodes.fix import apply_fix, human_review, propose_fix, run_tests
from .nodes.intake import analyze_bug, inspect_project
from .nodes.investigation import challenge_hypothesis, collect_evidence, generate_hypotheses, reproduce_bug
from .nodes.report import final_report
from .routing import ROUTES
from .state import BugReport, InvestigationState, RunOptions

log = logging.getLogger(__name__)

NODES = {
    "analyze_bug": analyze_bug,
    "inspect_project": inspect_project,
    "generate_hypotheses": generate_hypotheses,
    "collect_evidence": collect_evidence,
    "challenge_hypothesis": challenge_hypothesis,
    "reproduce_bug": reproduce_bug,
    "propose_fix": propose_fix,
    "human_review": human_review,
    "apply_fix": apply_fix,
    "run_tests": run_tests,
    "final_report": final_report,
}

# Expected, recoverable stops. They end the investigation with a partial report instead of a crash.
# (LangGraph's own interrupt signal is not in this list, so human_review still pauses normally.)
_STOPS = (BudgetExceeded, ReasoningFailed, WorkspaceError)


def _guarded(name: str, node):
    @wraps(node)
    def wrapped(state: InvestigationState, runtime: Rt) -> dict:
        try:
            return node(state, runtime)
        except _STOPS as exc:
            log.warning("node %s stopped the investigation: %s", name, exc)
            return {"halt_reason": f"{name}: {exc}"}
    return wrapped


def build_graph(checkpointer: BaseCheckpointSaver | None = None) -> CompiledStateGraph:
    graph = StateGraph(InvestigationState, context_schema=InvestigationContext)
    for name, node in NODES.items():
        graph.add_node(name, _guarded(name, node))

    graph.add_edge(START, "analyze_bug")
    graph.add_edge("analyze_bug", "inspect_project")
    graph.add_edge("inspect_project", "generate_hypotheses")
    for name, (router, destinations) in ROUTES.items():
        graph.add_conditional_edges(name, router, destinations)
    graph.add_edge("final_report", END)

    return graph.compile(checkpointer=checkpointer)


def initial_state(bug: BugReport, settings: Settings, mode: InvestigationMode | None = None) -> InvestigationState:
    return {
        "bug": bug,
        "options": RunOptions(
            mode=mode or settings.investigation_mode,
            max_hypothesis_rounds=settings.max_hypothesis_rounds,
            max_fix_attempts=settings.max_fix_attempts,
        ),
    }
