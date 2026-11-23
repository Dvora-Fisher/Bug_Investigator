"""The investigation State: everything the graph knows, passed from node to node and saved by the checkpointer.

Pydantic models describe the *content* (hypotheses, evidence, fixes...). They double as the
structured-output schemas the LLM must fill in, so each shape is defined exactly once.
"""

from __future__ import annotations

import operator
from typing import Annotated, Literal

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel, Field
from typing_extensions import TypedDict

from ..runtimes.base import Capability

# ----------------------------------------------------------------------------- input


class BugReport(BaseModel):
    description: str
    error_output: str = ""


class ProjectProfile(BaseModel):
    """Facts about the project gathered without the LLM (cheap, deterministic)."""

    tree: str
    file_count: int
    extensions: dict[str, int]
    manifests: list[str]
    runtime: str | None = Field(description="Name of the runtime adapter that matched, if any")
    capability: Capability


class RunOptions(BaseModel):
    """Per-investigation switches, stored in the state so every node and router sees the same values."""

    mode: Literal["baseline", "improved"]
    max_hypothesis_rounds: int
    max_fix_attempts: int


# ----------------------------------------------------------------------------- investigation


class Location(BaseModel):
    file: str
    symbol: str = Field(default="", description="Function / method / class name, if known")


class Hypothesis(BaseModel):
    id: str = Field(description="Short id such as H1, H2")
    statement: str = Field(description="What is wrong and why it produces the reported behaviour")
    location: Location
    status: Literal["open", "supported", "refuted"] = "open"
    confidence: float = Field(default=0.5, ge=0, le=1)


class Evidence(BaseModel):
    """A real observation produced by a tool call. The LLM cannot invent these; it can only cite them."""

    id: str = Field(description="E1, E2, ...")
    tool: str
    args: dict
    excerpt: str


class Finding(BaseModel):
    """The LLM's interpretation of evidence for one hypothesis."""

    hypothesis_id: str
    verdict: Literal["supported", "refuted", "inconclusive"]
    evidence_ids: list[str] = Field(description="Ids of the evidence items (E#) this verdict relies on")
    note: str


class Reproduction(BaseModel):
    attempted: bool
    reproduced: bool
    method: str
    evidence_ids: list[str] = Field(default_factory=list)


class FileEdit(BaseModel):
    path: str = Field(description="File path relative to the project root")
    old: str = Field(description="Exact existing text to replace (must appear exactly once in the file)")
    new: str = Field(description="Replacement text")


class ProposedFix(BaseModel):
    root_cause: str
    explanation: str = Field(description="Why this change fixes the root cause")
    edits: list[FileEdit]
    evidence_ids: list[str]
    diff: str = ""


class ReviewDecision(BaseModel):
    decision: Literal["approve", "reject"]
    feedback: str = ""
    # When rejecting: improve the fix, or go back and investigate other hypotheses.
    next_step: Literal["revise_fix", "reinvestigate"] = "revise_fix"


class TestRun(BaseModel):
    __test__ = False  # tell pytest this is not a test class

    command: str
    passed: bool
    exit_code: int | None
    output_excerpt: str


class Claim(BaseModel):
    text: str
    evidence_ids: list[str]

    @property
    def verified(self) -> bool:
        return bool(self.evidence_ids)


class FinalReport(BaseModel):
    bug: str
    outcome: Literal["fixed_and_verified", "fixed_unverified", "fix_failed", "no_fix", "stopped"]
    files: list[str]
    root_cause: str
    verified_facts: list[Claim]
    unverified_hypotheses: list[str]
    reproduction: str
    fix_summary: str
    diff: str
    tests: list[TestRun]
    notes: list[str]


# ----------------------------------------------------------------------------- graph state


class InvestigationState(TypedDict, total=False):
    options: RunOptions
    bug: BugReport
    referenced_files: list[str]
    profile: ProjectProfile
    language: str
    bug_summary: str
    hypotheses: list[Hypothesis]
    evidence: Annotated[list[Evidence], operator.add]  # append-only ledger
    findings: Annotated[list[Finding], operator.add]
    reproduction: Reproduction
    proposed_fix: ProposedFix
    review: ReviewDecision
    test_runs: Annotated[list[TestRun], operator.add]
    hypothesis_rounds: int
    fix_attempts: int
    halt_reason: str
    report: FinalReport


def checkpoint_serializer() -> JsonPlusSerializer:
    """A serializer that may only rebuild our own State types when loading a checkpoint.

    LangGraph refuses (or warns about) unknown classes in saved checkpoints so that a tampered
    checkpoint file cannot make the app construct arbitrary objects. We list our types explicitly.
    """
    ours = [t for t in globals().values()
            if isinstance(t, type) and issubclass(t, BaseModel) and t.__module__ == __name__]
    return JsonPlusSerializer(allowed_msgpack_modules=[(t.__module__, t.__name__) for t in [*ours, Capability]])


def evidence_by_id(state: InvestigationState) -> dict[str, Evidence]:
    return {e.id: e for e in state.get("evidence", [])}


def leading_hypothesis(state: InvestigationState) -> Hypothesis | None:
    """The best hypothesis that has not been refuted (supported first, then by confidence)."""
    candidates = [h for h in state.get("hypotheses", []) if h.status != "refuted"]
    if not candidates:
        return None
    return max(candidates, key=lambda h: (h.status == "supported", h.confidence))
