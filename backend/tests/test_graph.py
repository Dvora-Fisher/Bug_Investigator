"""End-to-end runs of the real graph with a scripted model (no API calls)."""

from __future__ import annotations

from investigator.budget import BudgetExceeded
from investigator.graph.nodes.fix import FixProposal
from investigator.graph.nodes.investigation import (
    ChallengeVerdict, EvidenceFindings, HypothesesOutput, NewHypothesis,
)
from investigator.graph.state import BugReport, FileEdit, Finding, Location, ReviewDecision
from investigator.sandbox.sources import LocalSource
from investigator.service import InvestigationService

from .conftest import FakeReasoner

BUG = BugReport(description="moving_average returns one value too few",
                error_output="File \"/ci/build/stats/moving.py\", line 9\nAssertionError")

HYPOTHESES = HypothesesOutput(language="Python", bug_summary="Off-by-one in moving_average", hypotheses=[
    NewHypothesis(statement="range() stops one window early", confidence=0.8,
                  location=Location(file="stats/moving.py", symbol="moving_average")),
])


def read_and_support(tools) -> EvidenceFindings:
    tools["read_file"].invoke({"path": "stats/moving.py", "start_line": 1, "end_line": 12})  # becomes E1
    return EvidenceFindings(findings=[
        Finding(hypothesis_id="H1", verdict="supported", evidence_ids=["E1"], note="range(len - window)")])


def fix(new: str = "range(len(values) - window + 1)") -> FixProposal:
    return FixProposal(root_cause="Loop bound excludes the last window", explanation="Add 1 to the bound",
                       edits=[FileEdit(path="stats/moving.py", old="range(len(values) - window)", new=new)],
                       evidence_ids=["E1"])


def happy_script(**overrides):
    script = {"generate_hypotheses": [HYPOTHESES], "collect_evidence": [read_and_support],
              "challenge_hypothesis": [ChallengeVerdict(holds=True, reason="E1 shows the bound")],
              "propose_fix": [fix()]}
    return FakeReasoner({**script, **overrides})


def run_until_pause(service: InvestigationService, source, mode=None) -> str:
    thread_id = service.create(LocalSource(source))
    list(service.start(thread_id, BUG, mode))
    return thread_id


def test_full_run_pauses_for_review_and_finishes_after_approval(make_service, sample_project):
    reasoner = happy_script()
    service = make_service(reasoner)
    tid = run_until_pause(service, sample_project)

    review = service.pending_review(tid)
    assert review is not None, "graph must stop at human_review"
    assert "+    for start in range(len(values) - window + 1):" in review["diff"]
    ws_file = service.settings.workspaces_dir / tid / "project" / "stats" / "moving.py"
    assert "window + 1" not in ws_file.read_text(), "nothing may be written before approval"

    list(service.resume(tid, ReviewDecision(decision="approve")))
    state = service.snapshot(tid).values
    report = state["report"]

    assert service.pending_review(tid) is None
    assert "window + 1" in ws_file.read_text()
    assert report.outcome == "fixed_unverified"  # no sandbox yet, and the report must say so
    assert report.files == ["stats/moving.py"]
    assert report.verified_facts and report.verified_facts[0].evidence_ids == ["E1"]
    assert any("NOT verified" in n for n in report.notes)
    assert state["referenced_files"] == ["stats/moving.py"]  # found from the stack trace
    assert reasoner.calls == ["generate_hypotheses", "collect_evidence", "challenge_hypothesis", "propose_fix"]


def test_rejected_fix_is_revised_with_feedback(make_service, sample_project):
    service = make_service(happy_script(propose_fix=[fix("range(len(values))"), fix()]))
    tid = run_until_pause(service, sample_project)

    list(service.resume(tid, ReviewDecision(decision="reject", feedback="index out of range", next_step="revise_fix")))
    second = service.pending_review(tid)
    assert second["attempt"] == 2 and "window + 1" in second["diff"]

    list(service.resume(tid, ReviewDecision(decision="approve")))
    assert service.snapshot(tid).values["report"].outcome == "fixed_unverified"


def test_reviewer_can_send_the_agent_back_to_investigate(make_service, sample_project):
    support_h2 = lambda tools: EvidenceFindings(findings=[  # noqa: E731
        Finding(hypothesis_id="H2", verdict="supported", evidence_ids=["E1"], note="second look")])
    service = make_service(happy_script(generate_hypotheses=[HYPOTHESES, HYPOTHESES],
                                        collect_evidence=[read_and_support, support_h2],
                                        challenge_hypothesis=[ChallengeVerdict(holds=True, reason="ok")] * 2,
                                        propose_fix=[fix(), fix()]))
    tid = run_until_pause(service, sample_project)
    list(service.resume(tid, ReviewDecision(decision="reject", feedback="look elsewhere", next_step="reinvestigate")))
    state = service.snapshot(tid).values
    assert state["hypothesis_rounds"] == 2
    assert [(h.id, h.status) for h in state["hypotheses"]] == [("H1", "refuted"), ("H2", "supported")]
    assert service.pending_review(tid) is not None


def test_baseline_mode_skips_the_challenge(make_service, sample_project):
    reasoner = happy_script()
    service = make_service(reasoner)
    run_until_pause(service, sample_project, mode="baseline")
    assert "challenge_hypothesis" not in reasoner.calls


def test_refuted_by_challenge_generates_new_hypotheses(make_service, sample_project):
    reasoner = happy_script(
        generate_hypotheses=[HYPOTHESES, HYPOTHESES],
        collect_evidence=[read_and_support, lambda tools: EvidenceFindings(findings=[
            Finding(hypothesis_id="H2", verdict="supported", evidence_ids=["E1"], note="again")])],
        challenge_hypothesis=[ChallengeVerdict(holds=False, reason="evidence is unrelated"),
                              ChallengeVerdict(holds=True, reason="ok")],
    )
    service = make_service(reasoner)
    tid = run_until_pause(service, sample_project)
    state = service.snapshot(tid).values
    assert [h.status for h in state["hypotheses"]] == ["refuted", "supported"]
    assert service.pending_review(tid) is not None


def test_citing_invented_evidence_stops_cleanly(make_service, sample_project):
    invented = EvidenceFindings(findings=[
        Finding(hypothesis_id="H1", verdict="supported", evidence_ids=["E99"], note="trust me")])
    service = make_service(happy_script(collect_evidence=[invented]))
    tid = run_until_pause(service, sample_project)
    report = service.snapshot(tid).values["report"]
    assert report.outcome == "stopped" and "E99" in report.notes[-1]


def test_budget_stop_produces_a_partial_report(make_service, sample_project):
    def over_budget(_tools):
        raise BudgetExceeded("Monthly budget reached")
    service = make_service(happy_script(generate_hypotheses=[over_budget]))
    tid = run_until_pause(service, sample_project)
    report = service.snapshot(tid).values["report"]
    assert report.outcome == "stopped" and any("Monthly budget" in n for n in report.notes)


def test_paused_investigation_survives_a_restart(settings, sample_project, caplog):
    """Pause, throw the service away, build a new one on the same SQLite file, resume."""
    settings.data_dir.mkdir(parents=True, exist_ok=True)

    def new_service():  # default checkpointer: SQLite file + our type allowlist
        return InvestigationService(settings, reasoner_factory=lambda _: happy_script())

    tid = run_until_pause(new_service(), sample_project)
    restarted = new_service()
    assert restarted.pending_review(tid) is not None
    list(restarted.resume(tid, ReviewDecision(decision="approve")))
    assert restarted.snapshot(tid).values["report"].outcome == "fixed_unverified"
    assert "unregistered type" not in caplog.text  # every State type is on the allowlist
