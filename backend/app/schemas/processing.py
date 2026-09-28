from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field

from app.schemas.common import ApiModel


class ProcessingRequest(ApiModel):
    """A request to process a video. The video is named in the path, so the body
    carries only the organization the caller believes it is acting in."""

    organization_id: uuid.UUID


class ProcessingJobRead(ApiModel):
    id: uuid.UUID
    organization_id: uuid.UUID
    video_id: uuid.UUID
    job_type: str
    status: Literal["queued", "running", "completed", "failed"]
    attempt: int
    max_attempts: int
    progress: float = Field(ge=0, le=100)
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


VideoStatusLiteral = Literal[
    "pending",
    "uploading",
    "uploaded",
    "stored",
    "processing",
    "ready",
    "failed",
]


class VideoProcessingRead(ApiModel):
    """The processing state of a video, for the polling fallback after a
    WebSocket reconnect.

    The CV counters are populated only once the corresponding stage has run, so
    an unprocessed video reports 'None' rather than a misleading zero.
    """

    video_id: uuid.UUID
    video_status: VideoStatusLiteral
    job: ProcessingJobRead | None
    analysis_run_id: uuid.UUID | None = None
    frames_processed: int | None = None
    detections: int | None = None
    tracks: int | None = None
