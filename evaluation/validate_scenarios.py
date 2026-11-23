"""Checks every scenario WITHOUT the LLM (no API cost):

  runnable scenarios:  visible + hidden tests FAIL on the buggy code, and PASS after the reference fix
  other scenarios:     the reference fix applies cleanly (the code cannot be executed)

A scenario that fails this check would make the evaluation meaningless: run it after editing any
scenario.   usage: python evaluation/validate_scenarios.py [scenario-id ...]
"""

from __future__ import annotations

import shutil
import sys
import uuid

from scenarios import Scenario, load_scenarios

from investigator.config import get_settings
from investigator.sandbox.docker_runner import DockerRunner
from investigator.sandbox.executor import Executor
from investigator.sandbox.workspace import Workspace, WorkspaceError


def validate(scenario: Scenario, runner: DockerRunner) -> tuple[bool, str]:
    settings = get_settings()
    base = settings.data_dir / "validation"
    ws = Workspace.create(base, uuid.uuid4().hex, scenario.project_dir, max_files=1000, max_bytes=10**7)
    try:
        if not scenario.runnable:
            ws.preview(scenario.reference_fix)
            return True, "not runnable here; reference fix applies"
        executor = Executor(runner, ws, scenario.adapter, settings)
        visible = executor.run_tests()
        scenario.add_hidden_tests(ws)
        before = executor.run_tests()
        if before.ok:
            return False, "tests PASS on the buggy code - the scenario does not expose the bug"
        ws.apply(scenario.reference_fix)
        after = executor.run_tests()
        if not after.ok:
            return False, f"tests still FAIL after the reference fix:\n{after.output[-1500:]}"
        return True, (f"visible tests {'pass' if visible.ok else 'fail'} before fix; "
                      f"all tests fail before / pass after the reference fix")
    finally:
        shutil.rmtree(ws.root, ignore_errors=True)


def main(ids: list[str]) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    runner = DockerRunner(get_settings())
    failures = 0
    for scenario in load_scenarios(ids or None):
        try:
            ok, detail = validate(scenario, runner)
        except WorkspaceError as exc:  # e.g. a reference fix that does not match the code
            ok, detail = False, f"reference fix does not apply: {exc}"
        failures += not ok
        print(f"{'OK  ' if ok else 'FAIL'} {scenario.id:<24} {scenario.spec['language']:<11} {detail}", flush=True)
    print(f"\n{failures} failing scenario(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
