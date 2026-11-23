"""Run-time dependencies handed to every node (LangGraph "context").

They are not part of the saved State: a workspace and an LLM client are live objects, rebuilt
for each run or resume. Tests pass a scripted reasoner here instead of a real model.
"""

from __future__ import annotations

from dataclasses import dataclass

from langgraph.runtime import Runtime

from ..config import Settings
from ..llm import Reasoner
from ..sandbox.workspace import Workspace


@dataclass
class InvestigationContext:
    workspace: Workspace
    reasoner: Reasoner
    settings: Settings


Rt = Runtime[InvestigationContext]
