"""Runs investigations in background threads and keeps a live, replayable log of what happened.

The graph itself decides when to pause (interrupt). This module only:
  * runs service.start / service.resume off the request thread,
  * turns every node update into an event (appended to <workspace>/events.jsonl),
  * lets HTTP clients wait for new events (server-sent events).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel
from pydantic_core import to_jsonable_python

from ..graph.state import BugReport
from ..service import InvestigationService

log = logging.getLogger(__name__)

# "activity" = a sandbox command started or ended inside a step (live progress; never ends a segment)
EventKind = Literal["started", "node", "activity", "paused", "done", "error", "cancelled"]
Status = Literal["running", "waiting_for_human", "done", "failed", "stopped", "cancelled"]
TERMINAL: frozenset[str] = frozenset({"paused", "done", "error", "cancelled"})  # a run segment ends with one of these


@dataclass(frozen=True)
class RunEvent:
    seq: int
    kind: EventKind
    node: str | None
    data: Any
    at: str


class EventLog:
    """Append-only event list for one investigation, mirrored to a JSONL file so it survives restarts."""

    def __init__(self, path: Path):
        self._path = path
        self._cond = threading.Condition()
        self._events: list[RunEvent] = []
        if path.exists():
            self._events = [RunEvent(**json.loads(line)) for line in path.read_text("utf-8").splitlines() if line]

    def append(self, kind: EventKind, node: str | None = None, data: Any = None) -> None:
        with self._cond:
            event = RunEvent(len(self._events) + 1, kind, node, to_jsonable_python(data),
                             datetime.now(UTC).isoformat())
            self._events.append(event)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(event)) + "\n")
            self._cond.notify_all()

    def after(self, seq: int, timeout: float = 0) -> list[RunEvent]:
        """Events with seq > given seq; waits up to `timeout` seconds for new ones if there are none."""
        with self._cond:
            if timeout and len(self._events) <= seq:
                self._cond.wait(timeout)
            return self._events[seq:]

    @property
    def last(self) -> RunEvent | None:
        return self._events[-1] if self._events else None


class RunManager:
    def __init__(self, service: InvestigationService):
        self.service = service
        self._lock = threading.Lock()
        self._logs: dict[str, EventLog] = {}
        self._running: set[str] = set()
        self._cancel_requested: set[str] = set()
        add_listener = getattr(service.runner, "add_listener", None)
        if add_listener:
            add_listener(self._on_sandbox)

    def _on_sandbox(self, workdir: Path, data: dict) -> None:
        """Sandbox progress (install / test runs can take minutes) -> an 'activity' event of that investigation."""
        try:
            thread_id = workdir.relative_to(self.service.settings.workspaces_dir.resolve()).parts[0]
        except (ValueError, IndexError):
            return  # not an investigation workspace (e.g. scenario validation)
        if (self.service.settings.workspaces_dir / thread_id / "meta.json").exists():
            self.events(thread_id).append("activity", data=data)

    # ------------------------------------------------------------------ commands

    def start(self, thread_id: str, bug: BugReport, mode: str | None) -> None:
        self._launch(thread_id, lambda: self.service.start(thread_id, bug, mode), "started")

    def resume(self, thread_id: str, answer: dict | BaseModel) -> None:
        """Validate the answer now (so the caller gets an error immediately), then continue in background."""
        if self.is_running(thread_id):
            raise RunInProgress(thread_id)
        if self.is_cancelled(thread_id):
            raise Cancelled(thread_id)
        value = self.service.validate_resume(thread_id, answer)
        self._launch(thread_id, lambda: self.service.resume(thread_id, value), "started",
                     {"resumed_with": value.model_dump()})

    def cancel(self, thread_id: str) -> Status:
        """Stop an investigation at the user's request.

        A running investigation stops at the next step boundary. A sandbox container that is running for it
        is killed at once; an LLM call in progress is allowed to finish (seconds). A paused one is closed at once.
        Nothing is ever applied to the code by cancelling. Returns the resulting status.
        """
        with self._lock:
            running = thread_id in self._running
            if running:
                self._cancel_requested.add(thread_id)
        if running:
            # Do not wait minutes for an install or test run to end: kill its sandbox container now.
            kill = getattr(self.service.runner, "kill_under", None)
            if kill:
                kill(self.service.settings.workspaces_dir / thread_id)
            return "running"
        status = self.status(thread_id)
        if status in ("done", "failed", "cancelled"):
            raise NotCancellable(thread_id, status)
        self.events(thread_id).append("cancelled", data={"message": "Cancelled by the user", "while": status})
        return "cancelled"

    # ------------------------------------------------------------------ queries

    def is_cancelled(self, thread_id: str) -> bool:
        last = self.events(thread_id).last
        return bool(last and last.kind == "cancelled")

    def is_running(self, thread_id: str) -> bool:
        with self._lock:
            return thread_id in self._running

    def events(self, thread_id: str) -> EventLog:
        with self._lock:
            if thread_id not in self._logs:
                path = self.service.settings.workspaces_dir / thread_id / "events.jsonl"
                self._logs[thread_id] = EventLog(path)
            return self._logs[thread_id]

    def status(self, thread_id: str) -> Status:
        if self.is_running(thread_id):
            return "running"
        if self.is_cancelled(thread_id):
            return "cancelled"
        snapshot = self.service.snapshot(thread_id)
        if any(task.interrupts for task in snapshot.tasks):
            return "waiting_for_human"
        if "report" in snapshot.values:
            return "done"
        last = self.events(thread_id).last
        return "failed" if last and last.kind == "error" else "stopped"

    def wait_until_idle(self, thread_id: str, timeout: float = 30) -> None:
        """For tests and scripts: block until the current run segment has finished."""
        deadline = time.monotonic() + timeout
        while self.is_running(thread_id):
            if time.monotonic() > deadline:
                raise TimeoutError(thread_id)
            time.sleep(0.02)

    # ------------------------------------------------------------------ internals

    def _launch(self, thread_id: str, stream: Callable[[], Iterator[dict]], kind: EventKind,
                data: Any = None) -> None:
        with self._lock:
            if thread_id in self._running:
                raise RunInProgress(thread_id)
            self._running.add(thread_id)
        self.events(thread_id).append(kind, data=data)
        threading.Thread(target=self._run, args=(thread_id, stream), daemon=True,
                         name=f"investigation-{thread_id[:8]}").start()

    def _run(self, thread_id: str, stream: Callable[[], Iterator[dict]]) -> None:
        events = self.events(thread_id)
        try:
            for update in stream():
                for node, data in update.items():
                    if node != "__interrupt__":
                        events.append("node", node, data)
                if thread_id in self._cancel_requested:
                    break  # leaving the loop closes the graph stream: no further step runs
            if thread_id in self._cancel_requested:
                events.append("cancelled", data={"message": "Cancelled by the user", "while": "running"})
            else:
                pause = self.service.pending_interrupt(thread_id)
                events.append("paused" if pause else "done", data=pause)
        except Exception as exc:  # report every failure to the client instead of losing it in a thread
            log.exception("investigation %s failed", thread_id)
            events.append("error", data={"message": f"{type(exc).__name__}: {exc}"})
        finally:
            with self._lock:
                self._running.discard(thread_id)
                self._cancel_requested.discard(thread_id)
            unblock = getattr(self.service.runner, "unblock", None)
            if unblock:
                unblock(self.service.settings.workspaces_dir / thread_id)


class RunInProgress(RuntimeError):
    """The investigation is already running; wait for it to pause or finish."""


class Cancelled(RuntimeError):
    """The investigation was cancelled by the user and cannot continue."""


class NotCancellable(RuntimeError):
    def __init__(self, thread_id: str, status: str):
        super().__init__(f"Investigation is already {status}")
        self.status = status
