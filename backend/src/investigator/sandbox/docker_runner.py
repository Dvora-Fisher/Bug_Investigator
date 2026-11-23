"""The ONLY place in the system that starts a container. Every execution gets the same limits:

  --network none          no internet (install steps are the single, fixed exception)
  --memory / --cpus       bounded resources;  --pids-limit  no fork bombs
  --read-only + tmpfs     the image cannot be modified; scratch space is in memory
  --cap-drop ALL, no-new-privileges, non-root user
  -v <workspace>:/workspace   only the investigation's copy of the project is visible
  timeout                 the container is killed when it runs too long

No host environment variables are passed in, so API keys and other secrets never reach the sandbox.
"""

from __future__ import annotations

import logging
import subprocess
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path

from ..config import Settings

log = logging.getLogger(__name__)


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
            timeout_s: int, env: Mapping[str, str] | None = None) -> ExecResult:
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
            *[arg for k, v in (env or {}).items() for arg in ("-e", f"{k}={v}")],
            image, *argv,
        ]
        shown = " ".join(argv)
        log.info("sandbox run (network=%s): %s", network, shown)
        start = time.monotonic()
        try:
            proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                  timeout=timeout_s, encoding="utf-8", errors="replace")
            return ExecResult(shown, proc.returncode, proc.stdout, False, time.monotonic() - start)
        except subprocess.TimeoutExpired as exc:
            subprocess.run(["docker", "kill", name], capture_output=True)
            partial = exc.stdout.decode("utf-8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            return ExecResult(shown, None, partial + f"\n[killed after {timeout_s}s]", True,
                              time.monotonic() - start)
