from __future__ import annotations

import uuid
from typing import cast

from fastapi import APIRouter, Query, status

from app.api.dependencies import CurrentUserDep, JobDispatcherDep, UnitOfWorkDep
from app.api.v1.presenters import processing_job_payload
from app.application.use_cases import processing as use_cases
from app.application.use_cases.organizations import require_organization_member
from app.core.errors import NotFoundError
from app.domain.shared import JobId, OrganizationId, VideoId
from app.schemas.common import ErrorResponse
from app.schemas.processing import (
    ProcessingJobRead,
    ProcessingRequest,
    VideoProcessingRead,
    VideoStatusLiteral,
)

router = APIRouter()


@router.post(
    "/videos/{video_id}/process",
    response_model=ProcessingJobRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue processing for a video",
    description=(
        "Creates a processing job for a video whose upload has completed and "
        "enqueues it. Returns immediately with '202 Accepted'. A repeated request "
        "returns the existing job rather than creating a second one."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Video not found."},
        409: {"model": ErrorResponse, "description": "Video cannot be processed."},
    },
)
async def request_processing(
    video_id: uuid.UUID,
    payload: ProcessingRequest,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    dispatcher: JobDispatcherDep,
) -> ProcessingJobRead:
    job = await use_cases.request_video_processing(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        user_id=user.id,
        video_id=VideoId(video_id),
        dispatcher=dispatcher,
    )
    return ProcessingJobRead.model_validate(processing_job_payload(job))


@router.get(
    "/processing-jobs/{job_id}",
    response_model=ProcessingJobRead,
    summary="Get a processing job",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_processing_job(
    job_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> ProcessingJobRead:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
    )
    job = await use_cases.get_processing_job(
        uow,
        organization_id=OrganizationId(organization_id),
        job_id=JobId(job_id),
    )
    return ProcessingJobRead.model_validate(processing_job_payload(job))


@router.get(
    "/videos/{video_id}/processing",
    response_model=VideoProcessingRead,
    summary="Get the processing state of a video",
    description=(
        "The current state a client reads after a WebSocket reconnect. The "
        "database is authoritative; events only prompt a refresh."
    ),
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_video_processing(
    video_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> VideoProcessingRead:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
    )
    state = await use_cases.get_video_processing_state(
        uow,
        organization_id=OrganizationId(organization_id),
        video_id=VideoId(video_id),
    )
    return VideoProcessingRead(
        video_id=state.video_id,
        video_status=cast(VideoStatusLiteral, state.video_status),
        job=(
            ProcessingJobRead.model_validate(processing_job_payload(state.job))
            if state.job is not None
            else None
        ),
        analysis_run_id=state.analysis_run.id if state.analysis_run is not None else None,
        frames_processed=state.frames_processed,
        detections=state.detections,
        tracks=state.tracks,
    )


@router.get(
    "/videos/{video_id}/processing/jobs",
    response_model=list[ProcessingJobRead],
    summary="List processing jobs for a video",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def list_video_processing_jobs(
    video_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> list[ProcessingJobRead]:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
    )
    async with uow:
        video = await uow.videos.get(VideoId(video_id))
        if video is None or video.organization_id != OrganizationId(organization_id):
            raise NotFoundError(f"Video {video_id} does not exist.")
        jobs = await uow.processing_jobs.list_for_video(VideoId(video_id))
    return [ProcessingJobRead.model_validate(processing_job_payload(job)) for job in jobs]
