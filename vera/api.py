from __future__ import annotations

import asyncio
import hmac
import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from . import __version__
from .config import Settings
from .schemas import ContextRequest, ReplyRequest, TickRequest
from .service import BotService, ServiceError
from .store import Store
from .utils import UTC, iso

logger = logging.getLogger("vera")


class RequestBoundary:
    """Bound raw request bytes (including chunked uploads) before JSON parsing."""
    def __init__(self, app, settings: Settings):
        self.app, self.settings = app, settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = {key.lower(): value for key, value in scope["headers"]}
        if scope["method"] in {"POST", "PUT", "PATCH"}:
            expected = self.settings.api_token
            if scope["path"] == "/v1/teardown" and self.settings.teardown_token:
                expected = self.settings.teardown_token
            actual = headers.get(b"authorization", b"").decode("latin1")
            if expected and not hmac.compare_digest(actual, "Bearer " + expected):
                return await JSONResponse({"accepted": False, "reason": "unauthorized"}, status_code=401)(scope, receive, send)
            content_type = headers.get(b"content-type", b"").decode("latin1").split(";", 1)[0].strip()
            if scope["path"] != "/v1/teardown" and content_type != "application/json":
                return await JSONResponse({"accepted": False, "reason": "content_type_must_be_json"}, status_code=415)(scope, receive, send)
            chunks, size = [], 0
            try:
                while True:
                    event = await asyncio.wait_for(receive(), timeout=15)
                    if event["type"] == "http.disconnect":
                        return
                    chunk = event.get("body", b"")
                    size += len(chunk)
                    if size > self.settings.max_body_bytes:
                        return await JSONResponse({"accepted": False, "reason": "payload_too_large"}, status_code=413)(scope, receive, send)
                    chunks.append(chunk)
                    if not event.get("more_body", False):
                        break
            except asyncio.TimeoutError:
                return await JSONResponse({"accepted": False, "reason": "body_timeout"}, status_code=408)(scope, receive, send)
            body = b"".join(chunks)
            delivered = False

            async def replay_receive():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": body, "more_body": False}
                return await receive()
            return await self.app(scope, replay_receive, send)
        return await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.store = Store(settings.db_path, settings.state_ttl_hours)
        app.state.service = BotService(app.state.store, settings)
        app.state.started = time.monotonic()
        app.state.started_at = iso(datetime.now(UTC))
        yield
        app.state.store.close()

    app = FastAPI(title="Vera Challenge Bot", version=__version__, lifespan=lifespan,
                  description="Deterministic, context-grounded challenge message engine. No real WhatsApp delivery or account changes.",
                  docs_url="/docs" if settings.docs_enabled else None, redoc_url=None)
    app.add_middleware(RequestBoundary, settings=settings)

    @app.exception_handler(ServiceError)
    async def service_error(request: Request, exc: ServiceError):
        return JSONResponse(exc.payload, status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        errors = [{"field": ".".join(str(p) for p in e["loc"]), "message": e["msg"]} for e in exc.errors()]
        reason = "invalid_scope" if any(e["loc"] == ("body", "scope") for e in exc.errors()) else "invalid_request"
        return JSONResponse({"accepted": False, "reason": reason, "details": errors}, status_code=400)

    @app.exception_handler(sqlite3.Error)
    async def database_error(request: Request, exc: sqlite3.Error):
        # Never log request payloads, messages or customer identity fields.
        logger.error("SQLite operation failed: %s", type(exc).__name__)
        return JSONResponse({"status": "error", "reason": "storage_unavailable"}, status_code=503)

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": "Vera Challenge Bot", "version": __version__, "health": "/v1/healthz", "metadata": "/v1/metadata", "docs": "/docs" if settings.docs_enabled else None}

    @app.get("/v1/healthz", tags=["Judge API"])
    @app.get("/healthz", include_in_schema=False)
    def healthz(request: Request):
        with request.app.state.store.transaction(activity=False) as db:
            counts = {"category": 0, "merchant": 0, "customer": 0, "trigger": 0}
            for row in db.execute("SELECT scope,COUNT(*) AS n FROM contexts GROUP BY scope"):
                counts[row["scope"]] = row["n"]
        return {"status": "ok", "uptime_seconds": int(time.monotonic() - request.app.state.started), "contexts_loaded": counts}

    @app.get("/v1/metadata", tags=["Judge API"])
    @app.get("/metadata", include_in_schema=False)
    def metadata(request: Request):
        return {"team_name": settings.team_name, "team_members": list(settings.team_members),
                "model": "deterministic-rule-engine-v1 (no external LLM)",
                "approach": "Context-grounded composer, priority routing, consent/session guards, transactional SQLite state and replay-safe reply state machine.",
                "contact_email": settings.contact_email, "version": __version__,
                "submitted_at": settings.submitted_at or request.app.state.started_at}

    @app.post("/v1/context", tags=["Judge API"])
    @app.post("/context", include_in_schema=False)
    def context(body: ContextRequest, request: Request):
        return request.app.state.service.push_context(body)

    @app.post("/v1/tick", tags=["Judge API"])
    @app.post("/tick", include_in_schema=False)
    def tick(body: TickRequest, request: Request):
        return request.app.state.service.tick(body)

    @app.post("/v1/reply", tags=["Judge API"])
    @app.post("/reply", include_in_schema=False)
    def reply(body: ReplyRequest, request: Request):
        return request.app.state.service.reply(body)

    @app.post("/v1/teardown", tags=["Lifecycle"])
    def teardown(request: Request):
        request.app.state.store.teardown()
        return {"accepted": True, "cleared": True}

    return app
