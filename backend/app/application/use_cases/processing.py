from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.application.ports.jobs import Job, JobDispatcher, JobKind
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.organizations import require_organization_writer
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun
from app.domain.jobs.entities import ProcessingJob
from app.domain.shared import JobId, OrganizationId, UserId, VideoId

PROCESS_VIDEO = JobKind.INGEST_VIDEO


@dataclass(frozen=True, slots=True)
class VideoProcessingState:
    video_id: VideoId
    video_status: str
    job: ProcessingJob | None
    analysis_run: AnalysisRun | None = None

    @property
    def detections(self) -> int | None:
        """Detections reported by the run's detection stage, if it has run."""
        return _stage_count(self.analysis_run, "detection", "detections")

    @property
    def tracks(self) -> int | None:
        """Distinct track identities reported by the tracking stage."""
        return _stage_count(self.analysis_run, "tracking", "track_ids")

    @property
    def frames_processed(self) -> int | None:
        return _stage_count(self.analysis_run, "detection", "frames_sampled")


def _stage_count(run: AnalysisRun | None, stage: str, key: str) -> int | None:
    if run is None:
        return None
    result = run.stage_results.get(stage)
    if not isinstance(result, dict):
        return None
    value = result.get(key)
    return int(value) if isinstance(value, int) else None


async def request_video_processing(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    video_id: VideoId,
    dispatcher: JobDispatcher,
) -> ProcessingJob:
    await require_organization_writer(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        video = await uow.videos.get(video_id)
        if video is None or video.organization_id != organization_id:
            # A cross-tenant probe must not be able to confirm that the id exists,
            # so this is reported as not-found rather than forbidden.
            raise NotFoundError(f"Video {video_id} does not exist.")

        if not video.is_processable:
            raise ConflictError(
                f"Video {video_id} is in state '{video.status}' and cannot be processed.",
                details={"video_status": str(video.status)},
            )

        # A repeated request returns the existing job rather than creating a
        # second one: two workers racing on one video would double the compute
        # for one result, and the idempotency key cannot dedupe a row that was
        # never created.
        active = await uow.processing_jobs.find_active(video_id, str(PROCESS_VIDEO))
        if active is not None:
            return active

    result = await dispatcher.dispatch(
        Job(
            kind=JobKind(str(PROCESS_VIDEO)),
            payload={"video_id": str(video_id)},
            organization_id=str(organization_id),
            idempotency_key=f"process:{video_id}",
        )
    )

    if not result.accepted or result.job_id is None:
        raise ConflictError("Processing could not be queued for this video.")

    async with uow:
        job = await uow.processing_jobs.get(JobId(_coerce_uuid(result.job_id)))
        if job is None:  # pragma: no cover - the dispatcher just persisted it
            raise ConflictError("Processing could not be queued for this video.")
        return job


async def get_processing_job(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    job_id: JobId,
) -> ProcessingJob:
    async with uow:
        job = await uow.processing_jobs.get(job_id)
        if job is None or job.organization_id != organization_id:
            raise NotFoundError(f"Processing job {job_id} does not exist.")
        return job


async def get_video_processing_state(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    video_id: VideoId,
) -> VideoProcessingState:
    async with uow:
        video = await uow.videos.get(video_id)
        if video is None or video.organization_id != organization_id:
            raise NotFoundError(f"Video {video_id} does not exist.")
        jobs = await uow.processing_jobs.list_for_video(video_id, limit=1)
        runs = await uow.analysis_runs.list_for_video(video_id)
        return VideoProcessingState(
            video_id=video_id,
            video_status=str(video.status),
            job=jobs[0] if jobs else None,
            analysis_run=runs[0] if runs else None,
        )


def _coerce_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
