from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.dependencies import (
    CurrentUserDep,
    JobDispatcherDep,
    SettingsDep,
    UnitOfWorkDep,
    VideoStorageDep,
)
from app.api.v1.params import Pagination, pagination
from app.api.v1.presenters import video_payload
from app.application.use_cases import videos as use_cases
from app.application.use_cases.organizations import require_organization_member
from app.core.errors import NotFoundError
from app.domain.shared import (
    MatchId,
    OrganizationId,
    VideoId,
)
from app.schemas.common import ErrorResponse
from app.schemas.videos import (
    VideoCompleteUpload,
    VideoList,
    VideoRead,
    VideoUploadRequest,
    VideoUploadTicket,
)

router = APIRouter()


@router.post(
    "",
    response_model=VideoUploadTicket,
    status_code=status.HTTP_201_CREATED,
    summary="Request a video upload slot",
    description=(
        "Reserves a storage key and returns a presigned URL. The client uploads "
        "the file bytes directly to object storage, then calls the 'complete' "
        "endpoint. Nothing about the video is inspected during this call."
    ),
)
async def request_upload(
    payload: VideoUploadRequest,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    storage: VideoStorageDep,
    settings: SettingsDep,
) -> VideoUploadTicket:
    ticket = await use_cases.request_video_upload(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        user_id=user.id,
        filename=payload.filename,
        content_type=payload.content_type,
        storage=storage,
        settings=settings,
        match_id=MatchId(payload.match_id) if payload.match_id else None,
    )
    return VideoUploadTicket(
        video_id=ticket.video_id,
        upload_url=ticket.upload_url,
        storage_key=ticket.storage_key,
        expires_in=ticket.expires_in,
    )


@router.post(
    "/{video_id}/complete",
    response_model=VideoRead,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Confirm an upload and schedule ingestion",
    description=(
        "Verifies that the object exists in storage, records the video and "
        "dispatches an ingestion job. Returns immediately — media probing and "
        "processing happen in a worker, never in this request."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Video or stored object not found."},
        409: {"model": ErrorResponse, "description": "Size mismatch or wrong state."},
    },
)
async def complete_upload(
    video_id: uuid.UUID,
    payload: VideoCompleteUpload,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    storage: VideoStorageDep,
    dispatcher: JobDispatcherDep,
    settings: SettingsDep,
) -> VideoRead:
    video = await use_cases.complete_video_upload(
        uow,
        organization_id=OrganizationId(payload.organization_id),
        user_id=user.id,
        video_id=VideoId(video_id),
        size_bytes=payload.size_bytes,
        checksum=payload.checksum,
        storage=storage,
        dispatcher=dispatcher,
        settings=settings,
    )
    return VideoRead.model_validate(video_payload(video))


@router.get("", response_model=VideoList, summary="List videos in an organization")
async def list_videos(
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
    page: Pagination = Depends(pagination),
) -> VideoList:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
    )
    async with uow:
        videos = await uow.videos.list_for_organization(
            OrganizationId(organization_id),
            limit=page.limit,
            offset=page.offset,
        )
    return VideoList(
        items=[VideoRead.model_validate(video_payload(video)) for video in videos],
        meta=page.meta(len(videos)),
    )


@router.get(
    "/{video_id}",
    response_model=VideoRead,
    summary="Get a video",
    responses={404: {"model": ErrorResponse, "description": "Not found."}},
)
async def get_video(
    video_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> VideoRead:
    await require_organization_member(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
    )
    async with uow:
        video = await uow.videos.get(VideoId(video_id))
    if video is None or video.organization_id != OrganizationId(organization_id):
        raise NotFoundError(f"Video {video_id} does not exist.")
    return VideoRead.model_validate(video_payload(video))


@router.delete(
    "/{video_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a video",
    description=(
        "Removes the video record and its stored object. The object deletion is "
        "best-effort: a storage failure does not keep the record in the library."
    ),
    responses={
        404: {"model": ErrorResponse, "description": "Not found."},
        403: {"model": ErrorResponse, "description": "Read-only role."},
    },
)
async def delete_video(
    video_id: uuid.UUID,
    user: CurrentUserDep,
    uow: UnitOfWorkDep,
    storage: VideoStorageDep,
    organization_id: uuid.UUID = Query(description="Owning organization."),
) -> Response:
    await use_cases.delete_video(
        uow,
        organization_id=OrganizationId(organization_id),
        user_id=user.id,
        video_id=VideoId(video_id),
        storage=storage,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
