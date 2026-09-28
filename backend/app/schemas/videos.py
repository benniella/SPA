"""Video request/response schemas.

Upload is two-step: 'POST /videos' returns a presigned URL so bytes go straight
to object storage, then 'POST /videos/{id}/complete' records the upload and
dispatches ingestion. Media probing happens in the worker, never in a request.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel, PageMeta


class VideoUploadRequest(ApiModel):
    organization_id: uuid.UUID
    filename: str = Field(min_length=1, max_length=512)
    content_type: str | None = Field(default=None, max_length=128)
    match_id: uuid.UUID | None = Field(
        default=None,
        description="Attach the recording to a match. Optional at upload time.",
    )


class VideoUploadTicket(ApiModel):
    """What the client needs in order to perform the upload itself."""

    video_id: uuid.UUID
    upload_url: str = Field(description="Presigned URL to PUT the video bytes to.")
    storage_key: str
    expires_in: int = Field(description="Seconds until the URL expires.")


class VideoCompleteUpload(ApiModel):
    """Client confirmation that the bytes landed in storage."""

    organization_id: uuid.UUID
    # Optional size check: if supplied and it disagrees with what storage
    # reports, the call fails rather than recording a truncated upload.
    size_bytes: int | None = Field(default=None, ge=0)
    checksum: str | None = Field(default=None, max_length=128)


class VideoRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    match_id: uuid.UUID | None
    original_filename: str
    status: Literal["pending", "uploading", "uploaded", "stored", "processing", "ready", "failed"]
    content_type: str | None
    size_bytes: int | None
    duration_seconds: float | None
    frame_rate: float | None
    width: int | None
    height: int | None
    codec: str | None
    failure_reason: str | None
    created_at: datetime
    updated_at: datetime


class VideoList(ApiModel):
    items: list[VideoRead]
    meta: PageMeta
