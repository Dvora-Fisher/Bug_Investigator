"""Steps 3-6: hypotheses, evidence, challenge, reproduction. This is where the LLM does the thinking."""

from __future__ import annotations

from pydantic import BaseModel, Field

from ...prompts import system_prompt
from ...runtimes.base import Capability
from ...tools.evidence import EvidenceRecorder, truncate
from ...tools.execution_tools import EXECUTION_TOOLS, build_execution_tools
from ...tools.project_tools import build_read_tools
from ..context import Rt
from ..render import bug_block, cited_evidence, evidence_block, hypotheses_block
from ..state import (
    Finding, Hypothesis, InvestigationState, Location, Reproduction, TestRun, leading_hypothesis,
)

REFERENCED_FILE_CHARS = 2500

# ----------------------------------------------------------------------------- LLM output schemas


class NewHypothesis(BaseModel):
    statement: str
    location: Location
    confidence: float = Field(ge=0, le=1)


class HypothesesOutput(BaseModel):
    language: str = Field(description="Main programming language of the project")
    bug_summary: str
    hypotheses: list[NewHypothesis] = Field(max_length=3)


class EvidenceFindings(BaseModel):
    """Submit your findings for the hypotheses you examined."""

    findings: list[Finding]


class ChallengeVerdict(BaseModel):
    holds: bool
    reason: str


class ReproductionReport(BaseModel):
    """Submit whether the bug was reproduced, how, and the evidence ids of the runs that show it."""

    reproduced: bool
    method: str = Field(description="How the bug shows up (which test / script, what output)")
    evidence_ids: list[str]
    command: list[str] = Field(default_factory=list, description="The reproduction command you ran, if you "
                               "wrote a script; leave empty if the existing test suite shows the bug")


# ----------------------------------------------------------------------------- nodes


def generate_hypotheses(state: InvestigationState, runtime: Rt) -> dict:
    ctx = runtime.context
    profile = state["profile"]
    previous = state.get("hypotheses", [])
    # File excerpts only on the first round; later rounds rely on the findings (saves tokens).
    excerpts = "" if previous else "\n\n".join(
        f"### {f}\n```\n{truncate(ctx.workspace.read_text(f), REFERENCED_FILE_CHARS)}\n```"
        for f in state.get("referenced_files", [])
    )
    review = state.get("review")
    user = "\n\n".join(filter(None, [
        bug_block(state),
        f"## Project structure ({profile.file_count} files)\n{profile.tree}",
        f"## Build/manifest files\n{', '.join(profile.manifests) or '(none)'}",
        f"## Files named in the error output\n{excerpts}" if excerpts else "",
        f"## Earlier hypotheses\n{hypotheses_block(previous)}" if previous else "",
        _findings_block(state),
        f"## Reviewer feedback\n{review.feedback}" if review and review.decision == "reject" else "",
    ]))
    out = ctx.reasoner.structured("generate_hypotheses", system_prompt("hypotheses", state["options"].mode),
                                  user, HypothesesOutput)
    new = [Hypothesis(id=f"H{len(previous) + i}", statement=h.statement, location=h.location,
                      confidence=h.confidence) for i, h in enumerate(out.hypotheses, start=1)]
    return {
        "language": out.language,
        "bug_summary": out.bug_summary,
        "hypotheses": previous + new,
        "hypothesis_rounds": state.get("hypothesis_rounds", 0) + 1,
    }


def collect_evidence(state: InvestigationState, runtime: Rt) -> dict:
    ctx = runtime.context
    hypotheses = state["hypotheses"]
    open_ids = {h.id for h in hypotheses if h.status == "open"}
    known_ids = {e.id for e in state.get("evidence", [])}
    recorder = EvidenceRecorder(len(known_ids), ctx.settings.max_tool_output_chars)
    strict = state["options"].mode == "improved"

    def validate(out: EvidenceFindings) -> str | None:
        valid_evidence = known_ids | {e.id for e in recorder.items}
        for f in out.findings:
            if f.hypothesis_id not in open_ids:
                return f"Unknown or closed hypothesis id {f.hypothesis_id}. Open ids: {sorted(open_ids)}"
            if bad := [i for i in f.evidence_ids if i not in valid_evidence]:
                return f"Evidence ids {bad} do not exist. Cite only ids shown in tool results."
            if strict and not f.evidence_ids:
                return f"Finding for {f.hypothesis_id} cites no evidence. Gather and cite evidence."
        return None if out.findings else "Submit at least one finding."

    user = "\n\n".join(filter(None, [
        bug_block(state),
        f"## Open hypotheses\n{hypotheses_block(h for h in hypotheses if h.status == 'open')}",
        f"## Files named in the error output\n{', '.join(state.get('referenced_files', []))}"
        if state.get("referenced_files") else "",
    ]))
    out = ctx.reasoner.tool_loop(
        "collect_evidence", system_prompt("collect_evidence", state["options"].mode), user,
        build_read_tools(ctx.workspace, recorder), EvidenceFindings, ctx.settings.max_tool_steps, validate,
    )
    return {
        "hypotheses": _apply_verdicts(hypotheses, out.findings),
        "findings": out.findings,
        "evidence": recorder.items,
    }


def challenge_hypothesis(state: InvestigationState, runtime: Rt) -> dict:
    """A sceptical second look at the leading hypothesis, using only the evidence already collected."""
    leader = leading_hypothesis(state)
    if leader is None:
        return {}
    user = "\n\n".join([
        bug_block(state),
        f"## Leading hypothesis\n{hypotheses_block([leader])}",
        f"## Evidence cited for it\n{evidence_block(cited_evidence(state, leader.id))}",
    ])
    verdict = runtime.context.reasoner.structured(
        "challenge_hypothesis", system_prompt("challenge", state["options"].mode), user, ChallengeVerdict)
    finding = Finding(hypothesis_id=leader.id, verdict="supported" if verdict.holds else "refuted",
                      evidence_ids=[], note=f"Challenge: {verdict.reason}")
    return {"hypotheses": _apply_verdicts(state["hypotheses"], [finding]), "findings": [finding]}


def reproduce_bug(state: InvestigationState, runtime: Rt) -> dict:
    """Run the existing tests first (no LLM). The LLM then judges the output and, if the suite does not
    show the bug, may write and run a small reproduction script. It must cite execution evidence."""
    ctx = runtime.context
    profile = state["profile"]
    if profile.capability < Capability.RUN:
        reason = ("no runtime adapter for this language" if profile.runtime is None
                  else "the Docker sandbox is not available")
        return {"reproduction": Reproduction(attempted=False, reproduced=False, method=f"Not attempted: {reason}.")}

    executor = ctx.executor(profile.runtime)
    recorder = EvidenceRecorder(len(state.get("evidence", [])), ctx.settings.max_tool_output_chars)
    install = executor.install()
    if not install.ok:
        recorder.observe("install_dependencies", {}, install.render())
        return {"evidence": recorder.items, "reproduction": Reproduction(
            attempted=False, reproduced=False, evidence_ids=[recorder.items[-1].id],
            method="Not attempted: installing the project's dependencies failed (see evidence).")}

    baseline = executor.run_tests()
    baseline_text = recorder.observe("initial_test_run", {}, baseline.render())
    before = TestRun.from_exec(baseline, recorder.items[-1], phase="before_fix")

    def validate(r: ReproductionReport) -> str | None:
        execution_ids = {e.id for e in recorder.items if e.tool in EXECUTION_TOOLS}
        if r.reproduced and not set(r.evidence_ids) & execution_ids:
            return f"A reproduction must cite the output of a run. Execution evidence ids: {sorted(execution_ids)}"
        if bad := [i for i in r.evidence_ids if i not in {e.id for e in [*state.get('evidence', []), *recorder.items]}]:
            return f"Evidence ids {bad} do not exist."
        return None

    leader = leading_hypothesis(state)
    user = "\n\n".join(filter(None, [
        bug_block(state),
        f"## Leading hypothesis\n{hypotheses_block([leader])}" if leader else "",
        f"## Result of running the existing test suite\n{baseline_text}",
    ]))
    tools = [*build_read_tools(ctx.workspace, recorder), *build_execution_tools(executor, recorder)]
    report = ctx.reasoner.tool_loop("reproduce_bug", system_prompt("reproduce", state["options"].mode), user,
                                    tools, ReproductionReport, ctx.settings.max_repro_tool_steps, validate)
    return {
        "reproduction": Reproduction(attempted=True, **report.model_dump()),
        "evidence": recorder.items,
        "test_runs": [before],
    }


# ----------------------------------------------------------------------------- helpers


def _apply_verdicts(hypotheses: list[Hypothesis], findings: list[Finding]) -> list[Hypothesis]:
    verdicts = {f.hypothesis_id: f.verdict for f in findings if f.verdict != "inconclusive"}
    return [h.model_copy(update={"status": verdicts[h.id],
                                 "confidence": 0.9 if verdicts[h.id] == "supported" else 0.0})
            if h.id in verdicts else h for h in hypotheses]


def _findings_block(state: InvestigationState) -> str:
    findings = state.get("findings", [])
    if not findings:
        return ""
    return "## What was learned so far\n" + "\n".join(
        f"- {f.hypothesis_id}: {f.verdict} - {f.note}" for f in findings)
