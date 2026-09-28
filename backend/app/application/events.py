from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.domain.jobs.entities import JobStatus, ProcessingJob

SCHEMA_VERSION = 1


class ProcessingEventType:
    __slots__ = ("value",)

    QUEUED = "processing.queued"
    STARTED = "processing.started"
    PROGRESS = "processing.progress"
    COMPLETED = "processing.completed"
    FAILED = "processing.failed"

    ALLOWED = frozenset({QUEUED, STARTED, PROGRESS, COMPLETED, FAILED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown processing event: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ProcessingEventType):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


_STATUS_TO_EVENT = {
    JobStatus.QUEUED: ProcessingEventType.QUEUED,
    JobStatus.RUNNING: ProcessingEventType.STARTED,
    JobStatus.COMPLETED: ProcessingEventType.COMPLETED,
    JobStatus.FAILED: ProcessingEventType.FAILED,
}


@dataclass(frozen=True, slots=True)
class ProcessingEvent:
    event: str
    job_id: str
    video_id: str
    status: str
    progress: float
    timestamp: datetime
    error: str | None = None
    schema_version: int = SCHEMA_VERSION

    def to_payload(self) -> dict[str, Any]:
        return {
            "event": self.event,
            "schema_version": self.schema_version,
            "job_id": self.job_id,
            "video_id": self.video_id,
            "status": self.status,
            "progress": self.progress,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


def event_for_job(
    job: ProcessingJob,
    *,
    event_type: ProcessingEventType | None = None,
) -> ProcessingEvent:
    resolved = event_type or ProcessingEventType(_STATUS_TO_EVENT[job.status.value])
    return ProcessingEvent(
        event=str(resolved),
        job_id=str(job.id),
        video_id=str(job.video_id),
        status=str(job.status),
        progress=job.progress,
        timestamp=job.updated_at,
        error=job.error,
    )
