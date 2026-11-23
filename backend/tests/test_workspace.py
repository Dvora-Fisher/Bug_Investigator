from pathlib import Path

import pytest

from investigator.graph.state import FileEdit
from investigator.sandbox.policy import is_sensitive
from investigator.sandbox.workspace import Workspace, WorkspaceError


@pytest.fixture
def ws(tmp_path: Path, sample_project: Path) -> Workspace:
    return Workspace.create(tmp_path / "ws", "t1", sample_project, max_files=100, max_bytes=10**6)


def test_sensitive_and_generated_files_are_not_copied(ws: Workspace):
    files = list(ws.iter_files())
    assert "stats/moving.py" in files
    assert ".env" not in files
    assert not any(f.startswith("node_modules/") for f in files)


@pytest.mark.parametrize("path", ["../outside.txt", "../../etc/passwd", "stats/../../x", "..\\..\\x", "C:/Windows"])
def test_path_jail_blocks_escapes(ws: Workspace, path: str):
    with pytest.raises(WorkspaceError, match="outside"):
        ws.resolve(path)


def test_leading_slash_stays_inside_project(ws: Workspace):
    assert ws.resolve("/stats/moving.py") == ws.resolve("stats/moving.py")


def test_apply_diff_and_reset(ws: Workspace):
    edit = FileEdit(path="stats/moving.py", old="range(len(values) - window)",
                    new="range(len(values) - window + 1)")
    diff = ws.apply([edit])
    assert "+    for start in range(len(values) - window + 1):" in diff
    assert ws.changed_files() == ["stats/moving.py"]
    ws.reset()
    assert ws.changed_files() == [] and ws.diff() == ""


def test_edit_must_match_exactly_once(ws: Workspace):
    with pytest.raises(WorkspaceError, match="exactly once"):
        ws.preview([FileEdit(path="stats/moving.py", old="does not exist", new="x")])
    with pytest.raises(WorkspaceError, match="exactly once"):
        ws.preview([FileEdit(path="stats/moving.py", old="window", new="w")])  # appears many times


def test_preview_does_not_write(ws: Workspace):
    ws.preview([FileEdit(path="stats/moving.py", old="window <= 0", new="window < 1")])
    assert ws.changed_files() == []


def test_too_large_project_is_rejected(tmp_path: Path, sample_project: Path):
    with pytest.raises(WorkspaceError, match="too large"):
        Workspace.create(tmp_path / "ws", "t2", sample_project, max_files=1, max_bytes=10**6)


@pytest.mark.parametrize("name,expected", [
    (".env", True), (".env.production", True), ("id_rsa", True), ("server.pem", True),
    (".env.example", False), ("main.py", False), ("appsettings.json", False),
])
def test_sensitive_patterns(name: str, expected: bool):
    assert is_sensitive(name) is expected
