"""Step 11: the final report, assembled in code from the State (no LLM call, so no new claims).

Facts vs. hypotheses is decided mechanically:
  * a verified fact is a conclusion that cites real evidence (tool output) or a real test run;
  * everything else is listed as an unverified hypothesis.
"""

from __future__ import annotations

from ...runtimes.base import Capability
from ..context import Rt
from ..state import Claim, FinalReport, InvestigationState, leading_hypothesis


def final_report(state: InvestigationState, runtime: Rt) -> dict:
    hypotheses = state.get("hypotheses", [])
    findings = state.get("findings", [])
    fix = state.get("proposed_fix")
    review = state.get("review")
    tests = state.get("test_runs", [])
    repro = state.get("reproduction")
    profile = state.get("profile")
    leader = leading_hypothesis(state)
    applied = bool(fix and review and review.decision == "approve")

    by_id = {h.id: h for h in hypotheses}
    facts = [Claim(text=f"{by_id[f.hypothesis_id].statement} ({f.note})", evidence_ids=f.evidence_ids)
             for f in findings if f.verdict == "supported" and f.evidence_ids and f.hypothesis_id in by_id]
    if repro and repro.reproduced:
        facts.append(Claim(text=f"Bug reproduced: {repro.method}", evidence_ids=repro.evidence_ids))
    backed = {f.hypothesis_id for f in findings if f.verdict == "supported" and f.evidence_ids}
    unverified = [f"{h.id}: {h.statement}" for h in hypotheses if h.status != "refuted" and h.id not in backed]

    notes = [f"Ruled out {h.id}: {h.statement}" for h in hypotheses if h.status == "refuted"]
    if profile and profile.capability < Capability.VERIFY:
        notes.append("Tests could not be run for this project, so the fix is NOT verified "
                     f"(runtime: {profile.runtime or 'none detected'}).")
    if halt := state.get("halt_reason"):
        notes.append(f"Investigation stopped early: {halt}")
    if fix and not applied:
        notes.append("A fix was proposed but not approved, so it was not applied.")

    return {"report": FinalReport(
        bug=state.get("bug_summary") or state["bug"].description,
        outcome=_outcome(state, applied),
        files=sorted({e.path for e in fix.edits}) if fix else ([leader.location.file] if leader else []),
        root_cause=fix.root_cause if fix else (f"(unverified) {leader.statement}" if leader else "Not determined"),
        verified_facts=facts,
        unverified_hypotheses=unverified,
        reproduction=repro.method if repro else "Not attempted.",
        fix_summary=fix.explanation if fix else "No fix was produced.",
        diff=fix.diff if applied else "",
        tests=tests,
        notes=notes,
    )}


def _outcome(state: InvestigationState, applied: bool) -> str:
    if state.get("halt_reason"):
        return "stopped"
    if not applied:
        return "no_fix"
    tests = state.get("test_runs", [])
    if not tests:
        return "fixed_unverified"
    return "fixed_and_verified" if tests[-1].passed else "fix_failed"
