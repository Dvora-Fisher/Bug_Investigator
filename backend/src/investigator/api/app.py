"""FastAPI application.  Run with:  uvicorn investigator.api.app:app --port 8000"""

from __future__ import annotations

import hmac
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from ..config import get_settings
from ..service import InvestigationService
from .routes import router
from .runs import RunManager


def create_app(service: InvestigationService | None = None) -> FastAPI:
    settings = service.settings if service else get_settings()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    app = FastAPI(title="Bug Investigator API", version="0.1.0")
    app.state.manager = RunManager(service or InvestigationService(settings))
    if settings.app_password:
        password = settings.app_password.encode()

        @app.middleware("http")
        async def require_password(request: Request, call_next):
            # Preflight requests carry no credentials; the CORS middleware (added after, so it runs first) answers them.
            if (request.url.path.startswith("/api") and request.url.path != "/api/ping"
                    and request.method != "OPTIONS"):
                given = request.headers.get("x-app-password") or request.query_params.get("key") or ""
                if not hmac.compare_digest(given.encode(), password):
                    return JSONResponse({"detail": "Password required"}, status_code=401)
            return await call_next(request)

    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins,
                       allow_origin_regex=settings.cors_origin_regex, allow_methods=["*"], allow_headers=["*"])
    app.include_router(router)
    return app


def __getattr__(name: str):
    """`app` is created on first access, so importing this module (e.g. in tests) has no side effects."""
    if name == "app":
        globals()["app"] = create_app()
        return globals()["app"]
    raise AttributeError(name)
