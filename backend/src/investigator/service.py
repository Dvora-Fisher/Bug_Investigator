"""One façade for running investigations, shared by the CLI now and the web API later.

It owns the long-lived pieces (compiled graph, checkpointer, usage ledger) and builds the
per-run context (workspace + reasoner) for a given thread_id.
"""

from __future__ import annotations

import sqlite3
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command, StateSnapshot

from .budget import UsageLedger
from .config import InvestigationMode, Settings
from .graph.builder import build_graph, initial_state
from .graph.context import InvestigationContext
from pydantic import BaseModel

from .graph.state import RESUME_SCHEMAS, BugReport, checkpoint_serializer
from .llm import LLMReasoner, Reasoner
from .sandbox.docker_runner import DockerRunner
from .sandbox.executor import Runner
from .sandbox.sources import ProjectSource, create_workspace
from .sandbox.workspace import Workspace

ReasonerFactory = Callable[[str], Reasoner]  # thread_id -> reasoner


class NotWaitingForHuman(RuntimeError):
    """A resume was requested for an investigation that is not paused at an interrupt."""


class InvestigationService:
    def __init__(self, settings: Settings, checkpointer: BaseCheckpointSaver | None = None,
                 reasoner_factory: ReasonerFactory | None = None, runner: Runner | None | bool = True):
        """runner=True builds the real Docker runner; pass None to disable execution, or a fake for tests."""
        self.settings = settings
        self.runner = DockerRunner(settings) if runner is True else runner or None
        self.ledger = UsageLedger(settings.usage_db, settings)
        if checkpointer is None:
            checkpointer = SqliteSaver(sqlite3.connect(settings.checkpoint_db, check_same_thread=False),
                                       serde=checkpoint_serializer())
        self.graph = build_graph(checkpointer)
        self._reasoner_factory = reasoner_factory or (lambda tid: LLMReasoner(settings, self.ledger, tid))

    # ------------------------------------------------------------------ lifecycle

    def create(self, source: ProjectSource) -> str:
        """Copy the project into a fresh workspace and return the new investigation's thread_id."""
        thread_id = uuid.uuid4().hex
        create_workspace(source, thread_id, self.settings)
        return thread_id

    def start(self, thread_id: str, bug: BugReport, mode: InvestigationMode | None = None) -> Iterator[dict[str, Any]]:
        return self._stream(thread_id, initial_state(bug, self.settings, mode))

    def validate_resume(self, thread_id: str, answer: dict | BaseModel) -> BaseModel:
        """Check an answer against the pause the graph is actually waiting on (before resuming anything)."""
        pending = self.pending_interrupt(thread_id)
        if pending is None:
            raise NotWaitingForHuman(f"Investigation {thread_id} is not waiting for a human")
        data = answer.model_dump() if isinstance(answer, BaseModel) else answer
        return RESUME_SCHEMAS[pending["type"]].model_validate(data)  # raises ValidationError on a mismatch

    def resume(self, thread_id: str, answer: dict | BaseModel) -> Iterator[dict[str, Any]]:
        value = self.validate_resume(thread_id, answer)
        return self._stream(thread_id, Command(resume=value.model_dump()))

    # ------------------------------------------------------------------ queries

    def snapshot(self, thread_id: str) -> StateSnapshot:
        return self.graph.get_state(self._config(thread_id))

    def pending_interrupt(self, thread_id: str) -> dict | None:
        """The interrupt payload if this investigation is waiting for a human, else None."""
        interrupts = [i for task in self.snapshot(thread_id).tasks for i in task.interrupts]
        return interrupts[0].value if interrupts else None

    def cost_usd(self, thread_id: str) -> float:
        return self.ledger.thread_cost_usd(thread_id)

    # ------------------------------------------------------------------ internals

    @staticmethod
    def _config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "run_name": "investigation",
                "metadata": {"thread_id": thread_id}}

    def _stream(self, thread_id: str, payload: Any) -> Iterator[dict[str, Any]]:
        context = InvestigationContext(
            workspace=Workspace.open(self.settings.workspaces_dir, thread_id),
            reasoner=self._reasoner_factory(thread_id),
            settings=self.settings,
            runner=self.runner,
        )
        yield from self.graph.stream(payload, self._config(thread_id), context=context, stream_mode="updates")
