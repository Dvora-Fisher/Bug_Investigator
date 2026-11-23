"""Steps 7-10: propose a fix, stop for human review, apply it, run the tests.

Proposing and applying are separate on purpose: propose_fix only *describes* edits (validated
in memory); nothing is written to disk until a human approves and apply_fix runs.
"""

from __future__ import annotations

from langgraph.types import interrupt
from pydantic import BaseModel, Field

from ...prompts import system_prompt
from ...runtimes.base import Capability
from ...sandbox.workspace import WorkspaceError
from ...tools.evidence import EvidenceRecorder
from ...tools.project_tools import build_read_tools
from ..context import Rt
from ..render import bug_block, cited_evidence, evidence_block, hypotheses_block
from ..state import (
    ClarificationAnswer, ClarificationRequest, FileEdit, Finding, FixReviewRequest, InvestigationState, ProposedFix, ReviewDecision, TestRun, after_fix_runs, leading_hypothesis,
)


class FixProposal(BaseModel):
    """Submit the fix: the exact edits first, then the evidence ids, root cause and explanation."""

    # Field order matters: in the experiments the model often submitted an empty edits list after
    # writing long explanations. Asking for the edits first, and requiring at least one, fixed that.
    edits: list[FileEdit] = Field(min_length=1)
    evidence_ids: list[str]
    root_cause: str
    explanation: str


def propose_fix(state: InvestigationState, runtime: Rt) -> dict:
    ctx = runtime.context
    ws = ctx.workspace
    ws.reset()  # a previous, failed fix must not leak into the next proposal
    leader = leading_hypothesis(state)
    known_ids = {e.id for e in state.get("evidence", [])}
    recorder = EvidenceRecorder(len(known_ids), ctx.settings.max_tool_output_chars)

    def validate(p: FixProposal) -> str | None:
        if not p.edits:
            return "Provide at least one edit."
        if bad := [i for i in p.evidence_ids if i not in known_ids | {e.id for e in recorder.items}]:
            return f"Evidence ids {bad} do not exist."
        try:
            ws.preview(p.edits)
        except WorkspaceError as exc:
            return str(exc)
        return None

    user = "\n\n".join(filter(None, [
        bug_block(state),
        f"## Leading hypothesis\n{hypotheses_block([leader])}" if leader else "",
        f"## Evidence\n{evidence_block(cited_evidence(state, leader.id))}" if leader else "",
        _history_block(state),
    ]))
    proposal = ctx.reasoner.tool_loop(
        "propose_fix", system_prompt("propose_fix", state["options"].mode), user,
        build_read_tools(ws, recorder), FixProposal, ctx.settings.max_fix_tool_steps, validate,
    )
    fix = ProposedFix(**proposal.model_dump(), diff=ws.diff_for(proposal.edits))
    return {"proposed_fix": fix, "evidence": recorder.items, "fix_attempts": state.get("fix_attempts", 0) + 1}


CLARIFICATION_QUESTION = ("You rejected the fix without saying why. What is wrong with it? "
                          "Should I revise the fix, or investigate a different cause?")


def human_review(state: InvestigationState, runtime: Rt) -> dict:
    """Pause the graph until a human approves or rejects the proposed fix.

    interrupt() saves the state in the checkpointer and stops. The run continues only when someone
    calls the graph again with Command(resume={...}) on the same thread_id; that value is returned here.
    A rejection without a reason triggers a second pause asking the human for clarification.
    (On resume LangGraph re-runs this node from the top and replays earlier answers in order,
    so the node must stay deterministic and side-effect free before each interrupt.)
    """
    fix = state["proposed_fix"]
    answer = interrupt(FixReviewRequest(
        attempt=state["fix_attempts"],
        max_attempts=state["options"].max_fix_attempts,
        root_cause=fix.root_cause,
        explanation=fix.explanation,
        diff=fix.diff,
        evidence_ids=fix.evidence_ids,
        verified_by_tests=state["profile"].capability >= Capability.VERIFY,
    ).model_dump())
    review = ReviewDecision.model_validate(answer)
    if review.decision == "reject" and not review.feedback.strip():
        clarification = ClarificationAnswer.model_validate(
            interrupt(ClarificationRequest(question=CLARIFICATION_QUESTION).model_dump()))
        review = review.model_copy(update={"feedback": clarification.answer,
                                           "next_step": clarification.next_step or review.next_step})
    update: dict = {"review": review}
    leader = leading_hypothesis(state)
    if review.decision == "reject" and review.next_step == "reinvestigate" and leader:
        # The human rejected the diagnosis itself: rule out the leading hypothesis so the
        # next round looks elsewhere instead of fixing the same thing again.
        finding = Finding(hypothesis_id=leader.id, verdict="refuted", evidence_ids=[],
                          note=f"Rejected by reviewer: {review.feedback or 'no reason given'}")
        update |= {"findings": [finding],
                   "hypotheses": [h.model_copy(update={"status": "refuted", "confidence": 0.0})
                                  if h.id == leader.id else h for h in state["hypotheses"]]}
    return update


def apply_fix(state: InvestigationState, runtime: Rt) -> dict:
    ws = runtime.context.workspace
    ws.reset()
    diff = ws.apply(state["proposed_fix"].edits)
    return {"proposed_fix": state["proposed_fix"].model_copy(update={"diff": diff})}


def run_tests(state: InvestigationState, runtime: Rt) -> dict:
    """Re-run the test suite (and the reproduction command, if one was written) after the fix.
    No LLM: pass/fail comes from exit codes, not from the model's opinion."""
    if state["profile"].capability < Capability.VERIFY:
        return {}  # nothing can be verified; the report says so explicitly
    ctx = runtime.context
    executor = ctx.executor(state["profile"].runtime)
    recorder = EvidenceRecorder(len(state.get("evidence", [])), ctx.settings.max_tool_output_chars)
    runs = []
    for tool, kind, result in _verification_runs(executor, state):
        recorder.observe(tool, {"attempt": state["fix_attempts"]}, result.render())
        runs.append(TestRun.from_exec(result, recorder.items[-1], phase="after_fix", kind=kind,
                                      attempt=state["fix_attempts"]))
    return {"test_runs": runs, "evidence": recorder.items}


def _verification_runs(executor, state: InvestigationState):
    yield "run_tests", "suite", executor.run_tests()
    repro = state.get("reproduction")
    if repro and repro.reproduced and repro.command:
        yield "run_command", "repro", executor.run_command(repro.command)


def _history_block(state: InvestigationState) -> str:
    """What went wrong before: failed test runs and reviewer feedback, so the next attempt can improve."""
    lines: list[str] = []
    review = state.get("review")
    if review and review.decision == "reject" and review.feedback:
        lines.append(f"- Reviewer rejected the previous fix: {review.feedback}")
    for run in after_fix_runs(state):
        if not run.passed:
            lines.append(f"- Tests failed after a previous fix (`{run.command}`):\n{run.output_excerpt}")
    return "## Previous attempts\n" + "\n".join(lines) if lines else ""
