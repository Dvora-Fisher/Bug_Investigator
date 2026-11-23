"""HTTP response shapes. They reuse the State models, so the API (and the TypeScript types generated
from its OpenAPI schema in the frontend) never drift from what the graph actually stores."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from ..graph.state import (
    BugReport, Evidence, FinalReport, Finding, Hypothesis, PauseRequest, ProjectProfile, ProposedFix,
    Reproduction, ReviewDecision, TestRun,
)
from .runs import Status

SourceType = Literal["sample", "zip", "github"]


class InvestigationMeta(BaseModel):
    thread_id: str
    created_at: datetime
    description: str
    source: str
    mode: Literal["baseline", "improved"]


class InvestigationSummary(InvestigationMeta):
    status: Status
    language: str | None = None
    outcome: str | None = None  # FinalReport.outcome once the investigation has finished
    cost_usd: float = 0.0


class InvestigationView(BaseModel):
    meta: InvestigationMeta
    status: Status
    pending: PauseRequest | None = None
    cost_usd: float
    # --- the investigation State (absent fields simply have not been produced yet) ---
    bug: BugReport | None = None
    bug_summary: str | None = None
    language: str | None = None
    profile: ProjectProfile | None = None
    hypotheses: list[Hypothesis] = []
    evidence: list[Evidence] = []
    findings: list[Finding] = []
    reproduction: Reproduction | None = None
    proposed_fix: ProposedFix | None = None
    review: ReviewDecision | None = None
    test_runs: list[TestRun] = []
    report: FinalReport | None = None
    halt_reason: str | None = None
    hypothesis_rounds: int = 0
    fix_attempts: int = 0


class Sample(BaseModel):
    id: str
    language: str
    category: str
    description: str
    error_output: str = ""


class Health(BaseModel):
    model: str
    docker: bool
    sandbox_images: dict[str, bool]
    month_spend_usd: float
    monthly_budget_usd: float


class ExperimentRow(BaseModel):
    scenario: str
    language: str
    scores: dict[str, float | None]
    outcome: str | None = None


class Experiment(BaseModel):
    name: str
    mode: Literal["baseline", "improved"]
    difficulty: Literal["basic", "hard"]
    finished_at: datetime
    scenarios: int
    total_spend_usd: float
    summary: dict[str, float | None]
    rows: list[ExperimentRow]


class Accepted(BaseModel):
    thread_id: str
    status: Status
