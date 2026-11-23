"""The ONLY place in the system that starts a container. Every execution gets the same limits:

  --network none          no internet (install steps are the single, fixed exception)
  --memory / --cpus       bounded resources;  --pids-limit  no fork bombs
  --read-only + tmpfs     the image cannot be modified; scratch space is in memory
  --cap-drop ALL, no-new-privileges, non-root user
  -v <workspace>:/workspace   only the investigation's copy of the project is visible
  -v <cache>:/cache       optional shared package cache: writable only for the fixed install
                          command, read-only while project code runs (so it cannot be poisoned)
  timeout                 the container is killed when it runs too long

No host environment variables are passed in, so API keys and other secrets never reach the sandbox.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from ..config import Settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Volume:
    """A named Docker volume mounted into the container (used for the shared package cache)."""

    name: str
    path: str
    read_only: bool


@dataclass(frozen=True)
class ExecResult:
    command: str
    exit_code: int | None  # None when the run timed out
    output: str
    timed_out: bool
    seconds: float

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def render(self) -> str:
        status = "TIMED OUT" if self.timed_out else f"exit code {self.exit_code}"
        return f"$ {self.command}\n[{status}, {self.seconds:.1f}s]\n{self.output}"


class DockerRunner:
    def __init__(self, settings: Settings):
        self._s = settings
        self._lock = threading.Lock()
        self._active: dict[str, Path] = {}  # container name -> workspace it runs in
        self._blocked: set[Path] = set()  # cancelled workspaces: no new container may start there
        self._listeners: list[Callable[[Path, dict], None]] = []

    def kill_under(self, root: Path) -> int:
        """Kill every running container whose workspace is inside `root` and refuse new ones there
        (used when a user cancels). Interrupted runs return a failure to their caller. Returns the kill count."""
        root = root.resolve()
        with self._lock:
            self._blocked.add(root)
            names = [n for n, w in self._active.items() if _inside(w, root)]
        for name in names:
            subprocess.run(["docker", "kill", name], capture_output=True)
        return len(names)

    def unblock(self, root: Path) -> None:
        with self._lock:
            self._blocked.discard(root.resolve())

    @cached_property
    def available(self) -> bool:
        try:
            return subprocess.run(["docker", "info", "--format", "{{.ServerVersion}}"],
                                  capture_output=True, timeout=20).returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def image_exists(self, image: str) -> bool:
        return self.available and subprocess.run(
            ["docker", "image", "inspect", image], capture_output=True).returncode == 0

    def run(self, image: str, argv: Sequence[str], workdir: Path, *, network: bool,
            timeout_s: int, env: Mapping[str, str] | None = None,
            volumes: Sequence[Volume] = ()) -> ExecResult:
        name = f"bug-investigator-{uuid.uuid4().hex[:12]}"
        cmd = [
            "docker", "run", "--rm", "--name", name,
            "--network", "bridge" if network else "none",
            "--memory", self._s.sandbox_memory, "--memory-swap", self._s.sandbox_memory,
            "--cpus", str(self._s.sandbox_cpus), "--pids-limit", str(self._s.sandbox_pids),
            "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            "--read-only", "--tmpfs", "/tmp:rw,exec,size=1g",
            "--user", "10001:10001",
            "-v", f"{workdir.resolve()}:/workspace:rw", "-w", "/workspace",
            *[arg for v in volumes for arg in ("-v", f"{v.name}:{v.path}:{'ro' if v.read_only else 'rw'}")],
            *[arg for k, v in (env or {}).items() for arg in ("-e", f"{k}={v}")],
            image, *argv,
        ]
        shown = " ".join(argv)
        log.info("sandbox run (network=%s): %s", network, shown)
        start = time.monotonic()
        with self._lock:
            if any(_inside(workdir.resolve(), b) for b in self._blocked):
                return ExecResult(shown, None, "[not run: the investigation was cancelled]", True, 0.0)
            self._active[name] = workdir.resolve()
        self._notify(workdir, {"phase": "start", "command": shown, "network": network, "timeout_s": timeout_s})
        result: ExecResult | None = None
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=timeout_s, encoding="utf-8", errors="replace")
            result = ExecResult(shown, proc.returncode, proc.stdout, False, time.monotonic() - start)
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "kill", name], capture_output=True)
            partial = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            result = ExecResult(shown, None, partial + f"\n[killed after {timeout_s}s]", True, time.monotonic() - start)
        finally:
            with self._lock:
                self._active.pop(name, None)
            self._notify(workdir, {"phase": "end", "command": shown, "network": network,
                                   "exit_code": result.exit_code if result else None,
                                   "timed_out": result.timed_out if result else False,
                                   "seconds": round(time.monotonic() - start, 1)})
        return result

    def add_listener(self, listener: Callable[[Path, dict], None]) -> None:
        """Called with (workdir, data) when a container starts and ends, e.g. to show live progress."""
        self._listeners.append(listener)

    def _notify(self, workdir: Path, data: dict) -> None:
        for listener in self._listeners:
            try:
                listener(workdir.resolve(), data)
            except Exception:  # progress reporting must never break a sandbox run
                log.exception("sandbox listener failed")


def _inside(path: Path, root: Path) -> bool:
    return path == root or root in path.parents
