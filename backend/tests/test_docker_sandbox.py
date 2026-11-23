"""Real containers: proves the isolation promises. Skipped when Docker or the images are missing.

    pytest -m docker
"""

from __future__ import annotations

import os

import pytest

from investigator.graph.state import FileEdit
from investigator.runtimes.adapters import PYTHON
from investigator.sandbox.docker_runner import DockerRunner
from investigator.sandbox.executor import Executor
from investigator.sandbox.workspace import Workspace

pytestmark = pytest.mark.docker


@pytest.fixture
def runner(settings):
    r = DockerRunner(settings)
    if not r.image_exists(PYTHON.image):
        pytest.skip("Docker or the python sandbox image is not available")
    return r


@pytest.fixture
def ws(tmp_path, sample_project):
    return Workspace.create(tmp_path / "ws", "d", sample_project, max_files=100, max_bytes=10**6)


def py(runner, ws, code: str, **kw):
    return runner.run(PYTHON.image, ["python", "-c", code], ws.project, network=kw.pop("network", False),
                      timeout_s=kw.pop("timeout_s", 60), env=PYTHON.env)


def test_no_network_by_default(runner, ws):
    r = py(runner, ws, "import socket; socket.create_connection(('1.1.1.1', 53), timeout=5)")
    assert not r.ok and ("Network is unreachable" in r.output or "OSError" in r.output)


def test_host_secrets_are_not_visible(runner, ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-should-never-leak")
    r = py(runner, ws, "import os; print(sorted(k for k in os.environ if 'KEY' in k or 'TOKEN' in k))")
    assert r.ok and "ANTHROPIC" not in r.output and "sk-ant" not in r.output
    assert os.environ["ANTHROPIC_API_KEY"]  # still set on the host side


def test_runs_as_non_root_on_a_read_only_image(runner, ws):
    r = py(runner, ws, "import os; print('uid', os.getuid(), flush=True); open('/etc/evil', 'w')")
    assert "uid 10001" in r.output and "Read-only file system" in r.output


def test_only_the_workspace_is_mounted(runner, ws):
    r = py(runner, ws, "import os; print(sorted(os.listdir('/workspace')))")
    assert r.ok and "stats" in r.output and "original" not in r.output


def test_timeout_kills_the_container(runner, ws):
    r = py(runner, ws, "import time; time.sleep(60)", timeout_s=3)
    assert r.timed_out and r.exit_code is None


def test_real_tests_fail_before_and_pass_after_the_fix(runner, ws, settings):
    executor = Executor(runner, ws, PYTHON, settings)
    assert executor.install().ok
    before = executor.run_tests()
    assert not before.ok and "2 failed" in before.output
    ws.apply([FileEdit(path="stats/moving.py", old="range(len(values) - window)",
                       new="range(len(values) - window + 1)")])
    after = executor.run_tests()
    assert after.ok and "2 passed" in after.output
