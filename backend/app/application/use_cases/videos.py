"""Video ingestion use cases.

The split is the asynchronous architecture in miniature: requesting an upload
reserves a storage key and creates the row without touching bytes, completing it
records what landed and dispatches an ingestion job, and requesting an analysis
run dispatches work. Probing and any other long-running step happen in the worker.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.application.ports.jobs import Job, JobDispatcher, JobKind
from app.application.ports.unit_of_work import UnitOfWork
from app.application.ports.video_storage import VideoStorage
from app.application.use_cases.organizations import require_organization_writer
from app.core.config import Settings
from app.core.errors import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    UnsupportedMediaError,
    ValidationError,
)
from app.domain.analysis.entities import (
    AnalysisPipelineSpec,
    AnalysisRun,
    default_pipeline,
)
from app.domain.shared import (
    MatchId,
    OrganizationId,
    UserId,
    VideoId,
    new_id,
)
from app.domain.videos.entities import Video, VideoStatus


@dataclass(frozen=True, slots=True)
class VideoUploadTicket:
    """Everything the client needs to perform the upload itself."""

    video_id: VideoId
    upload_url: str
    storage_key: str
    expires_in: int


async def request_video_upload(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    filename: str,
    content_type: str | None,
    storage: VideoStorage,
    settings: Settings,
    match_id: MatchId | None = None,
) -> VideoUploadTicket:
    """Reserve a storage location for an upload and record the intent.

    Returns a presigned URL so the client can send the bytes straight to object
    storage. Routing a 4 GB match recording through the API process would consume
    a worker for minutes and cap throughput at the number of API processes.

    Raises:
        PermissionDeniedError: the caller may not write to this organization.
        UnsupportedMediaError: the declared content type or size is not allowed.
        ValidationError: the attached match belongs to another organization.
    """
    await require_organization_writer(uow, organization_id=organization_id, user_id=user_id)

    if content_type is not None and content_type not in settings.allowed_video_content_types:
        raise UnsupportedMediaError(
            f"Unsupported content type: {content_type}.",
            details={"allowed": sorted(settings.allowed_video_content_types)},
        )

    if match_id is not None:
        async with uow:
            match = await uow.matches.get(match_id)
        if match is None or match.organization_id != organization_id:
            # Same reasoning as a cross-tenant video read: a match in another
            # workspace must not be attachable, and must not be confirmable.
            raise ValidationError(
                f"Match {match_id} does not exist in this organization.",
                details={"match_id": str(match_id)},
            )

    video_id = VideoId(new_id())
    storage_key = storage.build_key(
        str(organization_id),
        category="videos",
        owner_id=str(video_id),
        filename=filename,
    )

    video = Video(
        id=video_id,
        organization_id=organization_id,
        original_filename=filename,
        storage_key=storage_key,
        content_type=content_type,
        match_id=match_id,
    )
    video.mark_uploading()

    async with uow:
        await uow.videos.add(video)
        await uow.commit()

    upload_url = await storage.presign_upload(
        storage_key,
        content_type=content_type,
        expires_in=settings.upload_url_ttl_seconds,
    )

    return VideoUploadTicket(
        video_id=video.id,
        upload_url=upload_url,
        storage_key=storage_key,
        expires_in=settings.upload_url_ttl_seconds,
    )


async def complete_video_upload(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    video_id: VideoId,
    size_bytes: int | None,
    checksum: str | None,
    storage: VideoStorage,
    dispatcher: JobDispatcher,
    settings: Settings,
) -> Video:
    """Verify a completed upload and schedule media ingestion.

    The object is checked before the video is marked uploaded: the browser's
    claim that a transfer succeeded is not evidence that it did. The response is
    returned as soon as the job is dispatched; probing and processing happen in
    the worker.

    Raises:
        NotFoundError: the video does not exist in this organization.
        UnsupportedMediaError: the stored object's content type is not allowed.
        InvalidStateError: no object exists, or the upload was already recorded.
        ConflictError: the reported size disagrees with storage.
    """
    async with uow:
        video = await uow.videos.get(video_id)
        if video is None or video.organization_id != organization_id:
            raise NotFoundError(f"Video {video_id} does not exist.")

        # Idempotent: a retried completion of an already-uploaded video returns the
        # recorded state rather than re-verifying storage or dispatching a second
        # ingestion job. The worker's job is keyed by video id, so a duplicate
        # dispatch would be deduplicated there anyway; returning early avoids it.
        if video.status.value in {VideoStatus.UPLOADED, VideoStatus.STORED}:
            return video

        if video.status.value not in VideoStatus.AWAITING_UPLOAD:
            raise InvalidStateError(
                f"Video {video_id} is in state '{video.status}' and cannot be completed.",
                details={"video_status": str(video.status)},
            )

        stored = await storage.stat(video.storage_key)
        if stored is None:
            video.mark_failed("No object was found in storage for this upload.")
            await uow.videos.update(video)
            await uow.commit()
            raise InvalidStateError(
                f"No object found in storage for video {video_id}.",
                details={"storage_key": video.storage_key},
            )

        if stored.content_type and stored.content_type not in settings.allowed_video_content_types:
            video.mark_failed(f"Unsupported content type: {stored.content_type}.")
            await uow.videos.update(video)
            await uow.commit()
            raise UnsupportedMediaError(
                f"Unsupported content type: {stored.content_type}.",
                details={"allowed": sorted(settings.allowed_video_content_types)},
            )

        if size_bytes is not None and size_bytes != stored.size_bytes:
            video.mark_failed("The reported upload size did not match the stored object.")
            await uow.videos.update(video)
            await uow.commit()
            raise ConflictError(
                "Reported upload size does not match the stored object.",
                details={"reported": size_bytes, "stored": stored.size_bytes},
            )

        if stored.size_bytes > settings.max_upload_bytes:
            video.mark_failed("The uploaded file exceeds the configured maximum size.")
            await uow.videos.update(video)
            await uow.commit()
            raise UnsupportedMediaError(
                "Upload exceeds the configured maximum size.",
                details={"max_upload_bytes": settings.max_upload_bytes},
            )

        # The status transition is what makes the video analysable, so it must be
        # written before the job is dispatched: a worker that started first would
        # find the video still awaiting upload and refuse to process it.
        video.mark_uploaded(size_bytes=stored.size_bytes, content_type=stored.content_type)
        video.checksum = checksum
        await uow.videos.update(video)
        await uow.commit()

    await dispatcher.dispatch(
        Job(
            kind=JobKind(JobKind.INGEST_VIDEO),
            payload={"video_id": str(video_id)},
            organization_id=str(organization_id),
            idempotency_key=f"ingest:{video_id}",
        )
    )

    return video


async def delete_video(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    user_id: UserId,
    video_id: VideoId,
    storage: VideoStorage,
) -> None:
    """Remove a video record and its stored object.

    The row is deleted before the object, and the object deletion is best-effort:
    a storage failure must not leave the record in place, or the library would
    keep showing a video the user has removed.

    Raises:
        NotFoundError: the video does not exist in this organization.
        PermissionDeniedError: the caller may not write to this organization.
    """
    await require_organization_writer(uow, organization_id=organization_id, user_id=user_id)

    async with uow:
        video = await uow.videos.get(video_id)
        if video is None or video.organization_id != organization_id:
            raise NotFoundError(f"Video {video_id} does not exist.")
        storage_key = video.storage_key
        await uow.videos.delete(video)
        await uow.commit()

    await storage.delete(storage_key)


async def request_analysis_run(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    video_id: VideoId,
    dispatcher: JobDispatcher,
    pipeline: AnalysisPipelineSpec | None = None,
) -> AnalysisRun:
    """Create an analysis run for a video and hand it to the job dispatcher.

    Raises:
        NotFoundError: the video does not exist.
        ConflictError: the video is not in a state that can be analysed (for
            example its upload never completed).
    """
    async with uow:
        video = await uow.videos.get(video_id)
        if video is None:
            raise NotFoundError(f"Video {video_id} does not exist.")

        if video.organization_id != organization_id:
            # Deliberately reported as not-found rather than forbidden: a
            # cross-tenant probe must not confirm that the id exists.
            raise NotFoundError(f"Video {video_id} does not exist.")

        if not video.is_analysable:
            raise ConflictError(
                f"Video {video_id} is in state '{video.status}' and cannot be analysed yet.",
                details={"video_status": str(video.status)},
            )

        run = AnalysisRun(
            organization_id=organization_id,
            video_id=video_id,
            match_id=video.match_id,
            pipeline=pipeline or default_pipeline(),
        )
        run.queue()

        await uow.analysis_runs.add(run)
        await uow.commit()

    await dispatcher.dispatch(
        Job(
            kind=JobKind(JobKind.RUN_ANALYSIS),
            payload={
                "analysis_run_id": str(run.id),
                "video_id": str(video_id),
                "stages": list(run.pipeline.stages),
            },
            organization_id=str(organization_id),
            idempotency_key=f"analysis:{run.id}",
        )
    )

    return run


async def get_analysis_run(
    uow: UnitOfWork,
    *,
    organization_id: OrganizationId,
    run_id: str,
) -> AnalysisRun:
    """Load a run so the frontend can poll its progress."""
    async with uow:
        run = await uow.analysis_runs.get(run_id)  # type: ignore[arg-type]
        if run is None or run.organization_id != organization_id:
            raise NotFoundError(f"Analysis run {run_id} does not exist.")
        return run


def build_pipeline_from_payload(payload: dict[str, Any]) -> AnalysisPipelineSpec:
    """Reconstruct a pipeline spec from a job payload.

    Lives in the application layer, not the worker, so that the API and any
    future worker interpret the payload identically.
    """
    stages = tuple(str(stage) for stage in payload.get("stages", ()))
    return AnalysisPipelineSpec(
        stages=stages or default_pipeline().stages,
        model_versions=dict(payload.get("model_versions", {})),
        params=dict(payload.get("params", {})),
    )
