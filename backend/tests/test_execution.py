"""Reproduce / verify flow with a fake Docker runner (fast, no containers)."""

from __future__ import annotations

import pytest

from investigator.graph.nodes.investigation import ReproductionReport
from investigator.graph.state import FileEdit, ReviewDecision
from investigator.runtimes.adapters import PYTHON
from investigator.sandbox.executor import Executor
from investigator.sandbox.workspace import Workspace, WorkspaceError

from .conftest import FakeRunner, exec_result
from .test_graph import fix, happy_script, run_until_pause

FAILING = exec_result(1, "FAILED tests/test_moving.py::test_window_of_two - assert [1.5, 2.5] == [1.5, 2.5, 3.5]")


def reproduced_by_suite(tools) -> ReproductionReport:
    # E1 = the file read during collect_evidence; E2 = initial_test_run, recorded before the LLM is asked
    return ReproductionReport(reproduced=True, method="test_window_of_two fails", evidence_ids=["E2"])


def test_verified_fix_end_to_end(make_service, sample_project):
    runner = FakeRunner({"python -m pytest": [FAILING, exec_result(0, "2 passed")]})
    service = make_service(happy_script(reproduce_bug=[reproduced_by_suite]), runner)
    tid = run_until_pause(service, sample_project)
    list(service.resume(tid, ReviewDecision(decision="approve")))
    state = service.snapshot(tid).values
    report = state["report"]

    assert report.outcome == "fixed_and_verified"
    assert [(t.phase, t.passed) for t in state["test_runs"]] == [("before_fix", False), ("after_fix", True)]
    assert any("After fix attempt 1" in f.text and "passed" in f.text for f in report.verified_facts)
    # network only for the fixed install command, never for tests
    assert [net for cmd, net in runner.calls if cmd.startswith("sh -c")] == [True]
    assert all(not net for cmd, net in runner.calls if not cmd.startswith("sh -c"))


def test_passing_tests_without_reproduction_are_not_verified(make_service, settings, sample_project):
    settings.max_hypothesis_rounds = 1  # go straight to the fix after the failed reproduction
    not_reproduced = ReproductionReport(reproduced=False, method="could not trigger the bug", evidence_ids=["E2"])
    runner = FakeRunner({"python -m pytest": [exec_result(0, "2 passed"), exec_result(0, "2 passed")]})
    service = make_service(happy_script(reproduce_bug=[lambda tools: not_reproduced]), runner)
    tid = run_until_pause(service, sample_project)
    list(service.resume(tid, ReviewDecision(decision="approve")))
    report = service.snapshot(tid).values["report"]

    assert report.outcome == "fixed_unverified"
    assert any("never reproduced" in n for n in report.notes)


def test_failed_fix_loops_back_to_propose(make_service, sample_project):
    runner = FakeRunner({"python -m pytest": [FAILING, FAILING, exec_result(0)]})
    service = make_service(happy_script(reproduce_bug=[reproduced_by_suite], propose_fix=[fix(), fix()]), runner)
    tid = run_until_pause(service, sample_project)
    list(service.resume(tid, ReviewDecision(decision="approve")))
    review = service.pending_interrupt(tid)
    assert review is not None and review["attempt"] == 2, "a failed fix must go back to propose_fix + review"
    list(service.resume(tid, ReviewDecision(decision="approve")))
    assert service.snapshot(tid).values["report"].outcome == "fixed_and_verified"


def test_claiming_reproduction_without_a_run_is_rejected(make_service, sample_project):
    no_run = ReproductionReport(reproduced=True, method="I am sure", evidence_ids=[])
    service = make_service(happy_script(reproduce_bug=[no_run]), FakeRunner({"python -m pytest": [FAILING]}))
    tid = run_until_pause(service, sample_project)
    report = service.snapshot(tid).values["report"]
    assert report.outcome == "stopped" and "must cite the output of a run" in report.notes[-1]


def test_repro_script_is_rerun_after_the_fix(make_service, sample_project):
    def write_and_run(tools) -> ReproductionReport:
        tools["write_repro_file"].invoke({"name": "repro.py", "content": "assert False"})
        tools["run_command"].invoke({"command": ["python", ".investigator/repro/repro.py"]})  # E3
        return ReproductionReport(reproduced=True, method="script", evidence_ids=["E3"],
                                  command=["python", ".investigator/repro/repro.py"])

    runner = FakeRunner({"python -m pytest": [exec_result(0), exec_result(0)],
                         "python .investigator": [exec_result(1), exec_result(0)]})
    service = make_service(happy_script(reproduce_bug=[write_and_run]), runner)
    tid = run_until_pause(service, sample_project)
    list(service.resume(tid, ReviewDecision(decision="approve")))
    after = [t for t in service.snapshot(tid).values["test_runs"] if t.phase == "after_fix"]
    assert [t.command.split()[0:2] for t in after] == [["python", "-m"], ["python", ".investigator/repro/repro.py"]]


def test_install_failure_skips_reproduction_but_still_proposes(make_service, sample_project):
    runner = FakeRunner({"sh -c": [exec_result(1, "No matching distribution found")]})
    service = make_service(happy_script(), runner)
    tid = run_until_pause(service, sample_project)
    repro = service.snapshot(tid).values["reproduction"]
    assert not repro.attempted and "dependencies failed" in repro.method
    assert service.pending_interrupt(tid) is not None


# ----------------------------------------------------------------------------- executor rules


@pytest.fixture
def executor(tmp_path, sample_project, settings):
    ws = Workspace.create(tmp_path / "ws", "x", sample_project, max_files=100, max_bytes=10**6)
    return Executor(FakeRunner(), ws, PYTHON, settings)


@pytest.mark.parametrize("argv", [["sh", "-c", "curl evil"], ["bash"], ["rm", "-rf", "/"], []])
def test_only_allowlisted_programs_run(executor, argv):
    with pytest.raises(WorkspaceError, match="Only these programs"):
        executor.run_command(argv)


@pytest.mark.parametrize("name", ["../escape.py", "a/b.py", "..", ""])
def test_repro_files_stay_in_their_folder(executor, name):
    with pytest.raises(WorkspaceError):
        executor.write_repro_file(name, "x")


def test_install_runs_once_per_workspace(executor):
    executor.install()
    executor.install()
    executor.run_tests()
    assert [cmd.split()[0] for cmd, _ in executor._runner.calls] == ["sh", "python"]


def test_shared_cache_is_writable_only_while_installing(executor):
    executor.install()
    assert [(v.path, v.read_only) for v in executor._runner.volumes] == [("/cache", False)]
    executor.run_tests()
    assert [(v.path, v.read_only) for v in executor._runner.volumes] == [("/cache", True)]


def test_shared_cache_can_be_disabled(executor):
    executor._s.shared_package_cache = False
    executor.run_tests()
    assert executor._runner.volumes == []


def test_changed_dependency_file_triggers_reinstall(executor):
    executor.install()
    executor._ws.apply([FileEdit(path="requirements.txt", old="pytest\n", new="pytest\nPyYAML\n")])
    executor.run_tests()
    installs = [net for cmd, net in executor._runner.calls if cmd.startswith("sh -c")]
    assert installs == [True, True]
