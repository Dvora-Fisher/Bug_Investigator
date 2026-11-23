"""Shared test fixtures. Nothing here calls a real model or spends money."""

from __future__ import annotations

import os

# Unit tests must never send traces to LangSmith, whatever .env says (set before .env is loaded).
os.environ["LANGSMITH_TRACING"] = "false"

import shutil  # noqa: E402
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import BaseModel

from investigator.config import Settings
from investigator.graph.state import checkpoint_serializer
from investigator.llm import ReasoningFailed
from investigator.sandbox.docker_runner import ExecResult
from investigator.service import InvestigationService

SCENARIOS = Path(__file__).resolve().parents[2] / "evaluation" / "scenarios"

Scripted = BaseModel | Callable[[dict], BaseModel]  # a fixed answer, or a function of the tools by name


class FakeReasoner:
    """Replays scripted answers per step and runs the real validators, like the LLM loop does."""

    def __init__(self, script: dict[str, list[Scripted]]):
        self.script = {k: list(v) for k, v in script.items()}
        self.calls: list[str] = []

    def _next(self, step: str, tools: dict) -> BaseModel:
        self.calls.append(step)
        if not self.script.get(step):
            raise ReasoningFailed(f"no scripted answer for {step}")
        item = self.script[step].pop(0)
        return item(tools) if callable(item) else item

    def structured(self, step, system, user, schema):
        return self._next(step, {})

    def tool_loop(self, step, system, user, tools, submit_schema, max_steps, validate=None):
        result = self._next(step, {t.name: t for t in tools})
        if validate and (error := validate(result)):
            raise ReasoningFailed(f"{step}: {error}")
        return result


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(_env_file=None, data_dir=tmp_path / "data", investigation_mode="improved")


@pytest.fixture
def sample_project(tmp_path: Path) -> Path:
    """The py-off-by-one scenario plus things that must never reach a workspace."""
    dest = tmp_path / "sample"
    shutil.copytree(SCENARIOS / "py-off-by-one" / "project", dest)
    (dest / ".env").write_text("SECRET=1")
    (dest / "node_modules" / "pkg").mkdir(parents=True)
    (dest / "node_modules" / "pkg" / "index.js").write_text("x")
    return dest


class FakeRunner:
    """Stands in for Docker: returns scripted results per command prefix and records every call."""

    def __init__(self, results: dict[str, list[ExecResult]] | None = None):
        self.results = {k: list(v) for k, v in (results or {}).items()}
        self.calls: list[tuple[str, bool]] = []  # (command, network)

    def image_exists(self, image: str) -> bool:
        return True

    def run(self, image, argv, workdir, *, network, timeout_s, env=None, volumes=()) -> ExecResult:
        command = " ".join(argv)
        self.calls.append((command, network))
        self.volumes = list(volumes)
        for prefix, queue in self.results.items():
            if command.startswith(prefix) and queue:
                return replace(queue.pop(0), command=command)
        return ExecResult(command, 0, "ok", False, 0.1)


def exec_result(code: int, output: str = "") -> ExecResult:
    return ExecResult("cmd", code, output, False, 0.1)


@pytest.fixture
def make_service(settings: Settings):
    def factory(reasoner: FakeReasoner, runner: FakeRunner | None = None) -> InvestigationService:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        return InvestigationService(settings, checkpointer=InMemorySaver(serde=checkpoint_serializer()),
                                    reasoner_factory=lambda _: reasoner, runner=runner)
    return factory
