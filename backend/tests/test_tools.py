from pathlib import Path

import pytest

from investigator.runtimes.adapters import detect_runtime
from investigator.sandbox.workspace import Workspace
from investigator.tools.evidence import EvidenceRecorder, truncate
from investigator.tools.project_tools import build_read_tools


@pytest.fixture
def polyglot(tmp_path: Path) -> Workspace:
    src = tmp_path / "src"
    files = {
        "app.py": "def total(items):\n    return sum(items)\n",
        "Billing.cs": "public class Billing {\n    public decimal Total(Order o) { return 0; }\n}\n",
        "cart.ts": "export const total = (items: number[]) => items.length;\nfunction other() {}\n",
        "main.go": "package main\nfunc total(xs []int) int { return 0 }\n",
    }
    for name, text in files.items():
        (src / name).parent.mkdir(parents=True, exist_ok=True)
        (src / name).write_text(text)
    return Workspace.create(tmp_path / "ws", "p", src, max_files=100, max_bytes=10**6)


def _tools(ws: Workspace, start: int = 0):
    recorder = EvidenceRecorder(start, max_chars=4000)
    return {t.name: t for t in build_read_tools(ws, recorder)}, recorder


def test_every_tool_result_becomes_numbered_evidence(polyglot):
    tools, recorder = _tools(polyglot, start=4)
    out = tools["read_file"].invoke({"path": "app.py", "start_line": 2, "end_line": 2})
    assert out.startswith("[E5]") and "2 |     return sum(items)" in out
    tools["search_code"].invoke({"pattern": "total"})
    assert [e.id for e in recorder.items] == ["E5", "E6"]


def test_find_definitions_is_language_agnostic(polyglot):
    tools, _ = _tools(polyglot)
    out = tools["find_definitions"].invoke({"symbol": "total"})
    for f in ("app.py:1", "cart.ts:1", "main.go:2"):
        assert f in out
    assert "Billing.cs:2" in tools["find_definitions"].invoke({"symbol": "Total"})


def test_find_definitions_rejects_regex_injection(polyglot):
    tools, _ = _tools(polyglot)
    with pytest.raises(Exception):
        tools["find_definitions"].invoke({"symbol": ".*"})


def test_search_with_glob(polyglot):
    tools, _ = _tools(polyglot)
    out = tools["search_code"].invoke({"pattern": "total", "file_glob": "*.py"})
    assert "app.py" in out and "cart.ts" not in out


def test_truncate_keeps_head_and_tail():
    text = "HEAD" + "x" * 10_000 + "TAIL"
    short = truncate(text, 100)
    assert short.startswith("HEAD") and short.endswith("TAIL") and "omitted" in short


def test_runtime_detection(tmp_path: Path, sample_project: Path):
    assert detect_runtime(sample_project).name == "python"
    (tmp_path / "cs").mkdir()
    (tmp_path / "cs" / "App.csproj").write_text("<Project/>")
    assert detect_runtime(tmp_path / "cs").name == "dotnet"
    (tmp_path / "go").mkdir()
    (tmp_path / "go" / "go.mod").write_text("module x")
    assert detect_runtime(tmp_path / "go") is None  # analysable, but not runnable (yet)
