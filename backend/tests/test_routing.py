"""The graph's decisions, tested as plain functions of the State."""

import pytest

from investigator.graph import routing as r
from investigator.graph.state import Hypothesis, Location, Reproduction, ReviewDecision, RunOptions, TestRun


def state(mode="improved", **extra):
    return {"options": RunOptions(mode=mode, max_hypothesis_rounds=2, max_fix_attempts=3), **extra}


def hyp(status="open"):
    return Hypothesis(id="H1", statement="s", location=Location(file="f.py"), status=status)


def test_halt_always_goes_to_report():
    s = state(halt_reason="budget", hypotheses=[hyp()])
    assert all(router(s) == "final_report" for router, _ in r.ROUTES.values())


def test_challenge_only_in_improved_mode():
    assert r.after_evidence(state("improved", hypotheses=[hyp("supported")])) == "challenge_hypothesis"
    assert r.after_evidence(state("baseline", hypotheses=[hyp("supported")])) == "reproduce_bug"


def test_all_refuted_loops_back_until_rounds_run_out():
    refuted = [hyp("refuted")]
    assert r.after_challenge(state(hypotheses=refuted, hypothesis_rounds=1)) == "generate_hypotheses"
    assert r.after_challenge(state(hypotheses=refuted, hypothesis_rounds=2)) == "final_report"


@pytest.mark.parametrize("attempted,reproduced,rounds,expected", [
    (True, False, 1, "generate_hypotheses"),   # not reproduced: investigate again
    (True, False, 2, "propose_fix"),           # no rounds left: propose anyway (report flags it)
    (True, True, 1, "propose_fix"),
    (False, False, 1, "propose_fix"),          # runtime unsupported: analysis-only path
])
def test_after_reproduce(attempted, reproduced, rounds, expected):
    s = state(reproduction=Reproduction(attempted=attempted, reproduced=reproduced, method="m"),
              hypothesis_rounds=rounds)
    assert r.after_reproduce(s) == expected


@pytest.mark.parametrize("decision,next_step,attempts,expected", [
    ("approve", "revise_fix", 1, "apply_fix"),
    ("reject", "revise_fix", 1, "propose_fix"),
    ("reject", "revise_fix", 3, "final_report"),
    ("reject", "reinvestigate", 1, "generate_hypotheses"),
])
def test_after_review(decision, next_step, attempts, expected):
    s = state(review=ReviewDecision(decision=decision, next_step=next_step), fix_attempts=attempts,
              hypothesis_rounds=1)
    assert r.after_review(s) == expected


def test_failed_tests_retry_fix_at_most_three_times():
    failed = [TestRun(command="pytest", passed=False, exit_code=1, output_excerpt="")]
    assert r.after_tests(state(test_runs=failed, fix_attempts=2)) == "propose_fix"
    assert r.after_tests(state(test_runs=failed, fix_attempts=3)) == "final_report"
    passed = [TestRun(command="pytest", passed=True, exit_code=0, output_excerpt="")]
    assert r.after_tests(state(test_runs=passed, fix_attempts=1)) == "final_report"
