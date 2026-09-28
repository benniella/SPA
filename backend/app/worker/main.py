from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from typing import cast

from app.application.events import event_for_job
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.domain.jobs.entities import ProcessingJob
from app.infrastructure.database.engine import get_session_factory
from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
from app.infrastructure.jobs.keydb_queue import KeyDbJobQueue
from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline
from app.infrastructure.processing.metrics_pipeline import MetricsPipeline
from app.infrastructure.realtime.keydb_events import KeyDbEventPublisher
from app.infrastructure.storage.local import LocalVideoStorage
from app.worker.runner import JobWorker

logger = logging.getLogger(__name__)


def build_worker(settings: Settings) -> JobWorker:
    """Build a worker from configuration.

    Events are published to KeyDB rather than to a local hub: the API process,
    not the worker, holds the WebSocket connections, so the event has to cross a
    process boundary to reach a browser.
    """
    uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
    queue = KeyDbJobQueue(
        settings.keydb_url,
        database=settings.keydb_database,
        visibility_timeout_seconds=settings.job_visibility_timeout_seconds,
    )
    publisher = KeyDbEventPublisher(settings.keydb_url, database=settings.keydb_database)
    pending_publishes: set[asyncio.Task[None]] = set()

    def on_event(job: ProcessingJob) -> None:
        loop = asyncio.get_running_loop()
        task = loop.create_task(publisher.publish(str(job.organization_id), event_for_job(job)))
        pending_publishes.add(task)
        task.add_done_callback(pending_publishes.discard)

    return JobWorker(
        uow_factory=cast(UnitOfWorkFactory, uow_factory),
        queue=queue,
        pipeline=CvProcessingPipeline(
            settings=settings,
            storage=LocalVideoStorage(settings),
            uow_factory=cast(UnitOfWorkFactory, uow_factory),
        ),
        metrics_pipeline=MetricsPipeline(
            settings=settings,
            uow_factory=cast(UnitOfWorkFactory, uow_factory),
        ),
        on_event=on_event,
    )


async def run() -> None:
    settings = get_settings()
    configure_logging(settings)

    worker = build_worker(settings)
    stop = asyncio.Event()

    loop = asyncio.get_running_loop()
    for signame in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(signame, stop.set)

    logger.info(
        "SPA worker started",
        extra={
            "environment": settings.environment,
            "concurrency": settings.worker_concurrency,
            "job_backend": settings.job_backend,
        },
    )
    await worker.serve(concurrency=settings.worker_concurrency, stop=stop)
    logger.info("SPA worker stopped")


if __name__ == "__main__":
    asyncio.run(run())
