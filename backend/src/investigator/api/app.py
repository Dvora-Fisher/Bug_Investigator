"""FastAPI application.  Run with:  uvicorn investigator.api.app:app --port 8000"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from ..service import InvestigationService
from .routes import router
from .runs import RunManager


def create_app(service: InvestigationService | None = None) -> FastAPI:
    settings = service.settings if service else get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="Bug Investigator API", version="0.1.0")
    app.state.manager = RunManager(service or InvestigationService(settings))
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app


def __getattr__(name: str):
    """`app` is created on first access, so importing this module (e.g. in tests) has no side effects."""
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
