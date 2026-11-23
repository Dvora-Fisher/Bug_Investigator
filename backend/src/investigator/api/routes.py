"""HTTP endpoints. Thin by design: validation and wiring here, all investigation logic in the graph.

POST /api/investigations                 create a workspace (sample | ZIP upload | GitHub URL) and start
GET  /api/investigations                 list investigations
GET  /api/investigations/{id}            current state, status and pending pause (if any)
GET  /api/investigations/{id}/events     live progress as server-sent events (replayable with ?after=N)
POST /api/investigations/{id}/resume     answer the pending pause -> graph continues via Command(resume=...)
GET  /api/investigations/{id}/file       read one project file (for the UI's file viewer)
GET  /api/samples, /api/health
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import yaml
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from fastapi import Path as PathParam
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import ValidationError

from ..config import ROOT_DIR
from ..graph.state import BugReport
from ..runtimes.adapters import ADAPTERS
from ..sandbox.sources import GitHubSource, LocalSource, ProjectSource, ZipSource
from ..sandbox.workspace import Workspace, WorkspaceError
from ..service import NotWaitingForHuman
from .runs import TERMINAL, RunInProgress, RunManager
from .schemas import (
    Accepted, Health, InvestigationMeta, InvestigationSummary, InvestigationView, Sample, SourceType,
)

SCENARIOS_DIR = ROOT_DIR / "evaluation" / "scenarios"
# Thread ids are uuid4 hex. Validating the pattern stops ids like "..%2F.." from reaching the file system.
ThreadId = Annotated[str, PathParam(pattern=r"^[0-9a-f]{32}$")]

router = APIRouter(prefix="/api")


def manager(request: Request) -> RunManager:
    return request.app.state.manager


Manager = Annotated[RunManager, Depends(manager)]


# ----------------------------------------------------------------------------- investigations


@router.post("/investigations", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def create_investigation(
    runs: Manager,
    description: Annotated[str, Form(min_length=5)],
    source_type: Annotated[SourceType, Form()],
    error_output: Annotated[str, Form()] = "",
    mode: Annotated[str | None, Form(pattern="^(baseline|improved)$")] = None,
    sample_id: Annotated[str | None, Form()] = None,
    github_url: Annotated[str | None, Form()] = None,
    github_ref: Annotated[str | None, Form()] = None,
    file: Annotated[UploadFile | None, File()] = None,
) -> Accepted:
    settings = runs.service.settings
    upload: Path | None = None
    try:
        if source_type == "zip":
            upload = _save_upload(file, settings.data_dir / "uploads", settings.max_project_mb * 2**20)
        source = _source(source_type, sample_id, github_url, github_ref, upload)
        thread_id = runs.service.create(source)
    except WorkspaceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    finally:
        if upload:
            upload.unlink(missing_ok=True)

    meta = InvestigationMeta(thread_id=thread_id, created_at=datetime.now(UTC), description=description,
                             source=source.describe(), mode=mode or settings.investigation_mode)
    (settings.workspaces_dir / thread_id / "meta.json").write_text(meta.model_dump_json(), encoding="utf-8")
    runs.start(thread_id, BugReport(description=description, error_output=error_output), meta.mode)
    return Accepted(thread_id=thread_id, status="running")


@router.get("/investigations", response_model=list[InvestigationSummary])
def list_investigations(runs: Manager) -> list[InvestigationSummary]:
    metas = [_read_meta(p) for p in runs.service.settings.workspaces_dir.glob("*/meta.json")]
    return [InvestigationSummary(**m.model_dump(), status=runs.status(m.thread_id))
            for m in sorted(metas, key=lambda m: m.created_at, reverse=True)]


@router.get("/investigations/{thread_id}", response_model=InvestigationView)
def get_investigation(thread_id: ThreadId, runs: Manager) -> InvestigationView:
    meta = _meta_or_404(runs, thread_id)
    values = runs.service.snapshot(thread_id).values
    return InvestigationView(
        meta=meta, status=runs.status(thread_id), pending=runs.service.pending_interrupt(thread_id),
        cost_usd=runs.service.cost_usd(thread_id),
        **{k: v for k, v in values.items() if k in InvestigationView.model_fields},
    )


@router.get("/investigations/{thread_id}/events")
def stream_events(thread_id: ThreadId, runs: Manager, after: int = 0) -> StreamingResponse:
    """Server-sent events. The stream ends after a terminal event (paused / done / error);
    the client reconnects with ?after=<last seq> after it resumes the investigation."""
    _meta_or_404(runs, thread_id)
    log = runs.events(thread_id)

    def generate() -> Iterator[str]:
        seq = after
        while True:
            batch = log.after(seq, timeout=15)
            if not batch:
                if not runs.is_running(thread_id):
                    return  # nothing new and nothing running: the segment is over
                yield ": keep-alive\n\n"
                continue
            for event in batch:
                seq = event.seq
                payload = {"seq": event.seq, "node": event.node, "at": event.at, "data": event.data}
                yield f"id: {event.seq}\nevent: {event.kind}\ndata: {json.dumps(payload)}\n\n"
            if batch[-1].kind in TERMINAL and not runs.is_running(thread_id):
                return

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/investigations/{thread_id}/resume", status_code=status.HTTP_202_ACCEPTED, response_model=Accepted)
def resume_investigation(thread_id: ThreadId, answer: dict, runs: Manager) -> Accepted:
    """Answer the pending pause. The body must match the pause type: a ReviewDecision for
    'fix_review', a ClarificationAnswer for 'clarification'. Nothing runs if it does not."""
    _meta_or_404(runs, thread_id)
    try:
        runs.resume(thread_id, answer)
    except (NotWaitingForHuman, RunInProgress) as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc) or "Investigation is running") from exc
    except ValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)) from exc
    return Accepted(thread_id=thread_id, status="running")


@router.get("/investigations/{thread_id}/file", response_class=PlainTextResponse)
def read_project_file(thread_id: ThreadId, path: str, runs: Manager) -> str:
    _meta_or_404(runs, thread_id)
    try:
        return Workspace.open(runs.service.settings.workspaces_dir, thread_id).read_text(path)[:200_000]
    except WorkspaceError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc


# ----------------------------------------------------------------------------- misc


@router.get("/samples", response_model=list[Sample])
def list_samples() -> list[Sample]:
    samples = []
    for spec_file in sorted(SCENARIOS_DIR.glob("*/scenario.yaml")):
        spec = yaml.safe_load(spec_file.read_text(encoding="utf-8"))
        samples.append(Sample(id=spec["id"], language=spec["language"], category=spec["category"],
                              description=spec["bug"]["description"].strip(),
                              error_output=(spec["bug"].get("error_output") or "").strip()))
    return samples


@router.get("/health", response_model=Health)
def health(runs: Manager) -> Health:
    s = runs.service.settings
    runner = runs.service.runner
    return Health(
        model=s.llm_model,
        docker=bool(runner and getattr(runner, "available", False)),
        sandbox_images={a.name: bool(runner and runner.image_exists(a.image)) for a in ADAPTERS},
        month_spend_usd=round(runs.service.ledger.month_spend_usd(), 4),
        monthly_budget_usd=s.monthly_budget_usd,
    )


# ----------------------------------------------------------------------------- helpers


def _source(kind: str, sample_id: str | None, url: str | None, ref: str | None, upload: Path | None) -> ProjectSource:
    if kind == "github":
        if not url:
            raise WorkspaceError("github_url is required")
        return GitHubSource(url.strip(), (ref or "").strip() or None)
    if kind == "zip":
        return ZipSource(upload)
    ids = {p.parent.name for p in SCENARIOS_DIR.glob("*/scenario.yaml")}
    if sample_id not in ids:
        raise WorkspaceError(f"Unknown sample: {sample_id}")
    return LocalSource(SCENARIOS_DIR / sample_id / "project")


def _save_upload(file: UploadFile | None, folder: Path, max_bytes: int) -> Path:
    if file is None or not (file.filename or "").lower().endswith(".zip"):
        raise WorkspaceError("Upload a .zip file")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"{uuid.uuid4().hex}.zip"
    written = 0
    with target.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                out.close()
                target.unlink(missing_ok=True)
                raise WorkspaceError(f"ZIP is larger than {max_bytes // 2**20} MB")
            out.write(chunk)
    return target


def _read_meta(path: Path) -> InvestigationMeta:
    return InvestigationMeta.model_validate_json(path.read_text(encoding="utf-8"))


def _meta_or_404(runs: RunManager, thread_id: str) -> InvestigationMeta:
    meta_file = runs.service.settings.workspaces_dir / thread_id / "meta.json"
    if not meta_file.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investigation not found")
    return _read_meta(meta_file)
