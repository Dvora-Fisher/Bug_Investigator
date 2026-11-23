"""The deterministic evaluators and the claim audit used by the LangSmith experiments."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "evaluation"))

from evaluators import (  # noqa: E402
    bug_reproduced, file_localization, fix_success, function_localization, unsupported_claim_rate,
)
from run_experiment import audit_claims  # noqa: E402
from scenarios import load_scenarios  # noqa: E402

from investigator.graph.state import (  # noqa: E402
    Evidence, FileEdit, FinalReport, Finding, Hypothesis, Location, ProposedFix, Reproduction,
)

REF = {"file": "src/Crm/CustomerService.cs", "symbol": "DisplayName", "root_cause": "x", "fix": "y",
       "runnable": True}


def test_file_localization_accepts_fix_or_leading_hypothesis():
    assert file_localization({"files": ["src/Crm/CustomerService.cs"]}, REF)["score"] == 1.0
    assert file_localization({"files": [], "leading_file": "./src/crm/customerservice.cs"}, REF)["score"] == 1.0
    assert file_localization({"files": ["src/Other.cs"], "leading_file": ""}, REF)["score"] == 0.0


def test_function_localization():
    assert function_localization({"leading_symbol": "CustomerService.DisplayName"}, REF)["score"] == 1.0
    assert function_localization({"leading_symbol": "", "fix_diff": "public string DisplayName(int id)"},
                                 REF)["score"] == 1.0
    assert function_localization({}, {**REF, "symbol": ""})["score"] is None  # not applicable


def test_execution_metrics_are_not_applicable_when_not_runnable():
    ref = {**REF, "runnable": False}
    assert bug_reproduced({"reproduced": False}, ref)["score"] is None
    assert fix_success({"hidden_tests_passed": None}, ref)["score"] is None
    assert fix_success({"hidden_tests_passed": True}, REF)["score"] == 1.0


def _state(finding_ids, fix_ids, outcome="fixed_unverified", excerpt="CustomerService.cs line 16"):
    hyp = Hypothesis(id="H1", statement="null deref", location=Location(file="src/Crm/CustomerService.cs"))
    return {
        "hypotheses": [hyp],
        "evidence": [Evidence(id="E1", tool="read_file", args={"path": "src/Crm/CustomerService.cs"}, excerpt=excerpt),
                     Evidence(id="E2", tool="initial_test_run", args={}, excerpt="1 failed")],
        "findings": [Finding(hypothesis_id="H1", verdict="supported", evidence_ids=finding_ids, note="n")],
        "proposed_fix": ProposedFix(root_cause="rc", explanation="e", evidence_ids=fix_ids,
                                    edits=[FileEdit(path="src/Crm/CustomerService.cs", old="a", new="b")]),
        "reproduction": Reproduction(attempted=True, reproduced=True, method="m", evidence_ids=["E2"]),
        "report": FinalReport(bug="b", outcome=outcome, files=[], root_cause="rc", verified_facts=[],
                              unverified_hypotheses=[], reproduction="", fix_summary="", diff="", tests=[], notes=[]),
    }


def test_claims_backed_by_relevant_evidence_are_supported():
    claims = audit_claims(_state(["E1"], ["E1"]), hidden=True)
    assert [c["supported"] for c in claims] == [True, True, True]
    assert unsupported_claim_rate({"claims": claims})["score"] == 0.0


def test_claims_without_or_with_irrelevant_evidence_are_flagged():
    claims = audit_claims(_state([], ["E2"]), hidden=True)
    reasons = [c["reason"] for c in claims if not c["supported"]]
    assert reasons == ["no evidence cited", "cited evidence does not show the edited code"]
    assert unsupported_claim_rate({"claims": claims})["score"] == pytest.approx(2 / 3)


def test_claiming_verified_while_hidden_tests_fail_is_unsupported():
    claims = audit_claims(_state(["E1"], ["E1"], outcome="fixed_and_verified"), hidden=False)
    assert claims[-1] == {"claim": "fix verified", "evidence_ids": [], "supported": False,
                          "reason": "hidden tests fail although verified was claimed"}


def test_every_scenario_is_well_formed():
    scenarios = load_scenarios()
    assert len(scenarios) >= 20
    assert len({s.id for s in scenarios}) == len(scenarios)
    for s in scenarios:
        assert s.id == s.dir.name
        assert {"file", "root_cause", "fix"} <= set(s.expected)
        assert (s.project_dir / s.expected["file"]).is_file(), s.id
        assert s.reference_fix and (not s.runnable or s.hidden_dir.is_dir()), s.id
    languages = {s.spec["language"] for s in scenarios}
    assert {"Python", "C#", "JavaScript", "TypeScript"} <= languages
    assert sum(not s.runnable for s in scenarios) >= 2  # honesty checks for unsupported runtimes
