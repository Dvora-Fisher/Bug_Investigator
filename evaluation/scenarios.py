"""Loads the bug scenarios (evaluation/scenarios/<id>/) shared by validation, dataset upload and experiments.

Each scenario folder holds:
    scenario.yaml   bug report, expected location / root cause / fix, and a reference fix
    project/        the buggy project the agent investigates
    hidden/         extra tests the agent never sees; copied into the project after the investigation
                    to check whether the fix really works (not only against the visible tests)
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

import yaml

from investigator.graph.state import BugReport, FileEdit
from investigator.runtimes.adapters import detect_runtime
from investigator.runtimes.base import RuntimeAdapter
from investigator.sandbox.workspace import Workspace

SCENARIOS_DIR = Path(__file__).resolve().parent / "scenarios"


@dataclass(frozen=True)
class Scenario:
    dir: Path

    @cached_property
    def spec(self) -> dict:
        return yaml.safe_load((self.dir / "scenario.yaml").read_text(encoding="utf-8"))

    @property
    def id(self) -> str:
        return self.spec["id"]

    @property
    def project_dir(self) -> Path:
        return self.dir / "project"

    @property
    def hidden_dir(self) -> Path:
        return self.dir / "hidden"

    @property
    def bug(self) -> BugReport:
        return BugReport(description=self.spec["bug"]["description"].strip(),
                         error_output=(self.spec["bug"].get("error_output") or "").strip())

    @property
    def expected(self) -> dict:
        return self.spec["expected"]

    @property
    def expected_files(self) -> list[str]:
        """One file for most bugs; a list when the fix must touch several files."""
        files = self.expected["file"]
        return files if isinstance(files, list) else [files]

    @property
    def difficulty(self) -> str:
        return self.spec.get("difficulty", "basic")

    @property
    def reference_fix(self) -> list[FileEdit]:
        return [FileEdit(**e) for e in self.spec["reference_fix"]]

    @cached_property
    def adapter(self) -> RuntimeAdapter | None:
        return detect_runtime(self.project_dir)

    @property
    def runnable(self) -> bool:
        return self.adapter is not None

    def add_hidden_tests(self, ws: Workspace) -> list[str]:
        """Copy the hidden tests into a workspace (same relative paths). Returns the copied paths."""
        copied = []
        for src in sorted(p for p in self.hidden_dir.rglob("*") if p.is_file()) if self.hidden_dir.exists() else []:
            rel = src.relative_to(self.hidden_dir)
            target = ws.project / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, target)
            copied.append(rel.as_posix())
        return copied


def load_scenarios(ids: list[str] | None = None, difficulty: str | None = None) -> list[Scenario]:
    scenarios = [Scenario(p.parent) for p in sorted(SCENARIOS_DIR.glob("*/scenario.yaml"))]
    if difficulty:
        scenarios = [s for s in scenarios if s.difficulty == difficulty]
    if ids:
        unknown = set(ids) - {s.id for s in scenarios}
        if unknown:
            raise SystemExit(f"Unknown scenario ids: {sorted(unknown)}")
        scenarios = [s for s in scenarios if s.id in ids]
    return scenarios
