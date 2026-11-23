"""Runs a project's commands for one investigation: install once (with network), then tests and
allow-listed commands (without network). Combines the adapter (what to run) with the runner (how)."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Sequence
from fnmatch import fnmatch
from typing import Protocol

from ..config import Settings
from ..runtimes.base import CACHE_MOUNT, RuntimeAdapter
from .docker_runner import ExecResult, Volume
from .workspace import Workspace, WorkspaceError

_SAFE_NAME = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.-]{0,80}$")


class Runner(Protocol):
    def image_exists(self, image: str) -> bool: ...

    def run(self, image: str, argv: Sequence[str], workdir, *, network: bool, timeout_s: int,
            env=None, volumes: Sequence[Volume] = ()) -> ExecResult: ...


class Executor:
    def __init__(self, runner: Runner, ws: Workspace, adapter: RuntimeAdapter, settings: Settings):
        self._runner = runner
        self._ws = ws
        self._adapter = adapter
        self._s = settings
        self._marker = ws.private_dir / "install.json"

    def install(self) -> ExecResult:
        """Install dependencies; reuse the previous install while the dependency files are unchanged
        (a fix that edits e.g. requirements.txt triggers a fresh install)."""
        fingerprint = self._manifest_fingerprint()
        if self._marker.exists():
            saved = json.loads(self._marker.read_text(encoding="utf-8"))
            if saved.pop("fingerprint", None) == fingerprint:
                return ExecResult(**saved)
        result = self._run(self._adapter.install_cmd, network=True, timeout_s=self._s.sandbox_install_timeout_s)
        self._marker.parent.mkdir(parents=True, exist_ok=True)
        self._marker.write_text(json.dumps({**result.__dict__, "fingerprint": fingerprint}), encoding="utf-8")
        return result

    def run_tests(self, test_filter: str = "") -> ExecResult:
        self.install()  # no-op unless dependency files changed (e.g. by an applied fix)
        return self._run(self._adapter.test_command(test_filter))

    def _manifest_fingerprint(self) -> str:
        digest = hashlib.sha256()
        for rel in self._ws.iter_files():
            if any(fnmatch(rel.rsplit("/", 1)[-1], pattern) for pattern in self._adapter.manifests):
                digest.update(rel.encode() + b"\0" + (self._ws.project / rel).read_bytes())
        return digest.hexdigest()

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
        env, volumes = dict(self._adapter.env), []
        if self._s.shared_package_cache and self._adapter.cache_env:
            env |= self._adapter.cache_env
            # Writable only during the install step (network on, fixed command); read-only otherwise.
            volumes.append(Volume(self._adapter.cache_volume, CACHE_MOUNT, read_only=not network))
        return self._runner.run(self._adapter.image, argv, self._ws.project, network=network,
                                timeout_s=timeout_s or self._s.sandbox_run_timeout_s, env=env, volumes=volumes)
