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

EventKind = Literal["started", "node", "paused", "done", "error"]
Status = Literal["running", "waiting_for_human", "done", "failed", "stopped"]
TERMINAL: frozenset[str] = frozenset({"paused", "done", "error"})  # a run segment ends with one of these


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

    # ------------------------------------------------------------------ commands

    def start(self, thread_id: str, bug: BugReport, mode: str | None) -> None:
        self._launch(thread_id, lambda: self.service.start(thread_id, bug, mode), "started")

    def resume(self, thread_id: str, answer: dict | BaseModel) -> None:
        """Validate the answer now (so the caller gets an error immediately), then continue in background."""
        if self.is_running(thread_id):
            raise RunInProgress(thread_id)
        value = self.service.validate_resume(thread_id, answer)
        self._launch(thread_id, lambda: self.service.resume(thread_id, value), "started",
                     {"resumed_with": value.model_dump()})

    # ------------------------------------------------------------------ queries

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
            pause = self.service.pending_interrupt(thread_id)
            events.append("paused" if pause else "done", data=pause)
        except Exception as exc:  # report every failure to the client instead of losing it in a thread
            log.exception("investigation %s failed", thread_id)
            events.append("error", data={"message": f"{type(exc).__name__}: {exc}"})
        finally:
            with self._lock:
                self._running.discard(thread_id)


class RunInProgress(RuntimeError):
    """The investigation is already running; wait for it to pause or finish."""
