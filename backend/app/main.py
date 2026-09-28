"""FastAPI application factory and adapter wiring."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.v1 import api_router
from app.api.websocket import WebSocketAuthenticator, register_websocket_routes
from app.application.ports.job_queue import JobQueue
from app.application.ports.jobs import JobDispatcher
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.infrastructure.database.engine import dispose_engine, get_session_factory
from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.jobs.dispatcher import QueuedJobDispatcher, RecordingJobQueue
from app.infrastructure.jobs.keydb_queue import KeyDbJobQueue
from app.infrastructure.realtime.hub import InProcessEventHub
from app.infrastructure.realtime.keydb_events import KeyDbEventBridge
from app.infrastructure.storage.local import LocalVideoStorage

logger = logging.getLogger(__name__)

API_DESCRIPTION = """
**SPA — Sport Performance Analysis.** Turns sports video into structured
performance data.

All endpoints are versioned under '/api/v1' and every error uses the same
envelope: '{"error": {"code", "message", "details"}}'.

### Asynchronous processing

Video analysis is long-running and is **never** performed inside an HTTP request.

* 'POST /videos' reserves storage and returns a presigned URL.
* 'POST /videos/{id}/complete' records the upload and dispatches an ingestion job.
* 'POST /videos/{id}/process' queues a processing job and returns '202 Accepted'.
* 'GET /videos/{id}/processing' returns the current processing state.
* 'POST /analysis-runs' creates a run and returns '202 Accepted' with a
  'Location' header. Poll that URL for progress.

Processing progress is also delivered over an authenticated WebSocket at
'/ws/processing'. Events are notifications; the database is authoritative, so a
client that reconnects re-reads the processing state rather than relying on the
stream being complete.

The frontend talks to this API and never to PostgreSQL.
"""


def build_job_queue(settings: Settings) -> JobQueue:
    """Create the configured job queue.

    'queued' enqueues to KeyDB for a worker process. 'inline' records the
    enqueue without delivering it, for development without a running KeyDB — the
    job row is still written, so the asynchronous contract is still exercised.
    """
    if settings.job_backend == "queued":
        return KeyDbJobQueue(
            settings.keydb_url,
            database=settings.keydb_database,
            visibility_timeout_seconds=settings.job_visibility_timeout_seconds,
        )
    return RecordingJobQueue()


def build_job_dispatcher(settings: Settings, queue: JobQueue) -> JobDispatcher:
    """Create the job dispatcher bound to the configured queue.

    The unit-of-work factory satisfies the port structurally; mypy cannot prove
    it across the application/infrastructure split, so the cast documents the
    invariant the integration tests exercise (as in 'app.api.dependencies').
    """
    factory = cast(
        UnitOfWorkFactory,
        SqlAlchemyUnitOfWorkFactory(get_session_factory(settings)),
    )
    return QueuedJobDispatcher(factory, queue)


def build_video_storage(settings: Settings) -> LocalVideoStorage:
    """Create the object-storage adapter for the configured backend."""
    if settings.storage_backend == "s3":  # pragma: no cover - not implemented
        raise NotImplementedError(
            "The S3 storage backend is not implemented yet. Set STORAGE_BACKEND=local."
        )
    return LocalVideoStorage(settings)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown: build adapters, then release them."""
    settings: Settings = app.state.settings

    job_queue = build_job_queue(settings)
    app.state.job_queue = job_queue
    app.state.job_dispatcher = build_job_dispatcher(settings, job_queue)
    app.state.video_storage = build_video_storage(settings)

    event_hub = InProcessEventHub()
    app.state.event_hub = event_hub
    app.state.ws_authenticator = WebSocketAuthenticator(
        settings,
        SqlAlchemyUnitOfWorkFactory(get_session_factory(settings)),
    )

    # When jobs run in a worker process, its events arrive over KeyDB; the
    # bridge forwards them into this process's hub, which delivers them to the
    # connections it holds.
    bridge: KeyDbEventBridge | None = None
    if settings.job_backend == "queued":
        bridge = KeyDbEventBridge(settings.keydb_url, event_hub, database=settings.keydb_database)
        await bridge.start()

    logger.info(
        "SPA API started",
        extra={
            "environment": settings.environment,
            "job_backend": settings.job_backend,
            "storage_backend": settings.storage_backend,
        },
    )

    try:
        yield
    finally:
        if bridge is not None:
            await bridge.stop()
        await job_queue.close()
        # Release the connection pool so a reload does not leak connections.
        await dispose_engine()
        logger.info("SPA API stopped")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the ASGI application."""
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.project_name,
        description=API_DESCRIPTION,
        version="0.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        openapi_tags=[
            {"name": "health", "description": "Liveness and readiness probes."},
            {"name": "organizations", "description": "Tenancy workspaces."},
            {"name": "users", "description": "Identity records."},
            {"name": "teams", "description": "Squads within an organization."},
            {"name": "players", "description": "Athletes and squad registration."},
            {"name": "matches", "description": "Fixtures that organise everything else."},
            {"name": "videos", "description": "Source media and its upload lifecycle."},
            {"name": "processing", "description": "Asynchronous video-processing jobs."},
            {"name": "analysis", "description": "Asynchronous video-processing runs."},
            {"name": "reports", "description": "Generated analysis reports."},
            {"name": "uploads", "description": "Local storage transfer endpoints."},
        ],
    )
    app.state.settings = settings

    register_exception_handlers(app, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Location"],
    )

    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=settings.allowed_host_list or ["*"],
        )

    app.include_router(api_router, prefix=settings.api_v1_prefix)
    register_websocket_routes(app, settings)
    return app


app = create_app()
