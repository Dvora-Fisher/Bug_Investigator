"""Run-time dependencies handed to every node (LangGraph "context").

They are not part of the saved State: a workspace, an LLM client and a container runner are live
objects, rebuilt for each run or resume. Tests pass scripted fakes here instead of real ones.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.runtime import Runtime

from ..config import Settings
from ..llm import Reasoner
from ..runtimes.adapters import get_adapter
from ..sandbox.executor import Executor, Runner
from ..sandbox.workspace import Workspace


@dataclass
class InvestigationContext:
    workspace: Workspace
    reasoner: Reasoner
    settings: Settings
    runner: Runner | None = None  # None = execution unavailable (no Docker, or disabled)

    def sandbox_ready(self, image: str) -> bool:
        return bool(self.settings.execution_enabled and self.runner and self.runner.image_exists(image))

    def executor(self, runtime_name: str | None) -> Executor:
        adapter = get_adapter(runtime_name)
        if adapter is None or self.runner is None:
            raise RuntimeError("execution requested for a project without a runnable sandbox")
        return Executor(self.runner, self.workspace, adapter, self.settings)


Rt = Runtime[InvestigationContext]
