from __future__ import annotations

import logging
import uuid

from app.application.ports.job_queue import JobQueue
from app.application.ports.jobs import Job, JobResult
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.domain.jobs.entities import ProcessingJob
from app.domain.shared import JobId, OrganizationId, VideoId

logger = logging.getLogger(__name__)


class QueuedJobDispatcher:
    def __init__(self, uow_factory: UnitOfWorkFactory, queue: JobQueue) -> None:
        self._uow_factory = uow_factory
        self._queue = queue

    async def dispatch(self, job: Job) -> JobResult:
        organization_id = job.organization_id
        video_id = job.payload.get("video_id")
        if organization_id is None or video_id is None:
            # A job without tenancy or a subject cannot be authorized in the
            # worker, so it is rejected here rather than queued and discovered
            # later. The payload contract is identifiers-only by design.
            return JobResult(
                accepted=False,
                detail="A processing job requires organization_id and video_id.",
            )

        processing_job = ProcessingJob(
            organization_id=OrganizationId(uuid.UUID(str(organization_id))),
            video_id=VideoId(uuid.UUID(str(video_id))),
            job_type=str(job.kind),
            max_attempts=job.max_attempts,
        )
        # The job's own 'max_attempts' is authoritative: it is written here, at
        # creation, and read back by the worker. The worker does not carry a
        # second budget that could disagree with the row.

        uow = self._uow_factory()
        async with uow:
            await uow.processing_jobs.add(processing_job)
            await uow.commit()

        await self._queue.enqueue(str(processing_job.id))
        logger.info(
            "job enqueued",
            extra={
                "job_id": str(processing_job.id),
                "job_type": processing_job.job_type,
                "organization_id": str(processing_job.organization_id),
            },
        )
        return JobResult(accepted=True, job_id=str(processing_job.id))


class RecordingJobQueue:
    def __init__(self) -> None:
        self.enqueued: list[str] = []

    async def enqueue(self, job_id: str) -> None:
        self.enqueued.append(job_id)

    async def dequeue(self, *, timeout_seconds: int = 5) -> str | None:
        return None

    async def acknowledge(self, job_id: str) -> None:
        return None

    async def requeue(self, job_id: str) -> None:
        return None

    async def close(self) -> None:
        return None


def job_id_of(value: str) -> JobId:
    return JobId(uuid.UUID(value))
