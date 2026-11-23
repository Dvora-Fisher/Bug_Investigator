"""Runs a project's commands for one investigation: install once (with network), then tests and
allow-listed commands (without network). Combines the adapter (what to run) with the runner (how)."""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from typing import Protocol

from ..config import Settings
from ..runtimes.base import RuntimeAdapter
from .docker_runner import ExecResult
from .workspace import Workspace, WorkspaceError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,80}$")


class Runner(Protocol):
    def image_exists(self, image: str) -> bool: ...

    def run(self, image: str, argv: Sequence[str], workdir, *, network: bool, timeout_s: int,
            env=None) -> ExecResult: ...


class Executor:
    def __init__(self, runner: Runner, ws: Workspace, adapter: RuntimeAdapter, settings: Settings):
        self._runner = runner
        self._ws = ws
        self._adapter = adapter
        self._s = settings
        self._marker = ws.private_dir / "install.json"

    def install(self) -> ExecResult:
        """Install dependencies once per workspace; later calls return the stored result."""
        if self._marker.exists():
            return ExecResult(**json.loads(self._marker.read_text(encoding="utf-8")))
        result = self._run(self._adapter.install_cmd, network=True, timeout_s=self._s.sandbox_install_timeout_s)
        self._marker.parent.mkdir(parents=True, exist_ok=True)
        self._marker.write_text(json.dumps(result.__dict__), encoding="utf-8")
        return result

    def run_tests(self, test_filter: str = "") -> ExecResult:
        return self._run(self._adapter.test_command(test_filter))

    def run_command(self, argv: Sequence[str]) -> ExecResult:
        """Run an allow-listed program (no shell, no network). The LLM chooses only the arguments."""
        if not argv or argv[0] not in self._adapter.allowed_executables:
            raise WorkspaceError(f"Only these programs may be run: {sorted(self._adapter.allowed_executables)}")
        return self._run(argv)

    def write_repro_file(self, name: str, content: str) -> str:
        """Write a reproduction script into .investigator/repro/ (never into the project's own files)."""
        if not _SAFE_NAME.match(name):
            raise WorkspaceError("File name must be a plain name such as test_repro.py")
        path = self._ws.private_dir / "repro" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return f".investigator/repro/{name}"

    def _run(self, argv: Sequence[str], *, network: bool = False, timeout_s: int | None = None) -> ExecResult:
        return self._runner.run(self._adapter.image, argv, self._ws.project, network=network,
                                timeout_s=timeout_s or self._s.sandbox_run_timeout_s, env=self._adapter.env)
