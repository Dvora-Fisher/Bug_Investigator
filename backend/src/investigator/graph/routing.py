"""Every "where next?" decision of the graph, in one file.

Each router is a pure function of the State, so the whole decision logic can be unit-tested
without a model. Any node that hit a hard stop (budget, invalid model output...) sets
halt_reason, and every router then sends the run straight to the final report.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps

from .state import InvestigationState, latest_verification, leading_hypothesis

Router = Callable[[InvestigationState], str]
REPORT = "final_report"


def _halts_to_report(router: Router) -> Router:
    @wraps(router)
    def wrapped(state: InvestigationState) -> str:
        return REPORT if state.get("halt_reason") else router(state)
    return wrapped


def _rounds_left(state: InvestigationState) -> bool:
    return state.get("hypothesis_rounds", 0) < state["options"].max_hypothesis_rounds


def _fix_attempts_left(state: InvestigationState) -> bool:
    return state.get("fix_attempts", 0) < state["options"].max_fix_attempts


def _new_hypotheses_or_report(state: InvestigationState) -> str:
    return "generate_hypotheses" if _rounds_left(state) else REPORT


@_halts_to_report
def after_hypotheses(state: InvestigationState) -> str:
    return "collect_evidence" if any(h.status == "open" for h in state.get("hypotheses", [])) else REPORT


@_halts_to_report
def after_evidence(state: InvestigationState) -> str:
    if leading_hypothesis(state) is None:  # everything refuted
        return _new_hypotheses_or_report(state)
    return "challenge_hypothesis" if state["options"].mode == "improved" else "reproduce_bug"


@_halts_to_report
def after_challenge(state: InvestigationState) -> str:
    return "reproduce_bug" if leading_hypothesis(state) is not None else _new_hypotheses_or_report(state)


@_halts_to_report
def after_reproduce(state: InvestigationState) -> str:
    repro = state["reproduction"]
    if repro.attempted and not repro.reproduced and _rounds_left(state):
        return "generate_hypotheses"  # could not reproduce: look for other explanations
    return "propose_fix"


@_halts_to_report
def after_propose(state: InvestigationState) -> str:
    return "human_review"


@_halts_to_report
def after_review(state: InvestigationState) -> str:
    review = state["review"]
    if review.decision == "approve":
        return "apply_fix"
    if review.next_step == "reinvestigate":
        return _new_hypotheses_or_report(state)
    return "propose_fix" if _fix_attempts_left(state) else REPORT


@_halts_to_report
def after_apply(state: InvestigationState) -> str:
    return "run_tests"


@_halts_to_report
def after_tests(state: InvestigationState) -> str:
    if latest_verification(state) is False and _fix_attempts_left(state):
        return "propose_fix"  # the fix did not work: try again (bounded by max_fix_attempts)
    return REPORT


# node name -> (router, every destination it can return). The destinations feed the graph diagram.
ROUTES: dict[str, tuple[Router, list[str]]] = {
    "generate_hypotheses": (after_hypotheses, ["collect_evidence", REPORT]),
    "collect_evidence": (after_evidence, ["challenge_hypothesis", "reproduce_bug", "generate_hypotheses", REPORT]),
    "challenge_hypothesis": (after_challenge, ["reproduce_bug", "generate_hypotheses", REPORT]),
    "reproduce_bug": (after_reproduce, ["generate_hypotheses", "propose_fix", REPORT]),
    "propose_fix": (after_propose, ["human_review", REPORT]),
    "human_review": (after_review, ["apply_fix", "propose_fix", "generate_hypotheses", REPORT]),
    "apply_fix": (after_apply, ["run_tests", REPORT]),
    "run_tests": (after_tests, ["propose_fix", REPORT]),
}
