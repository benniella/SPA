from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import (
    JobId,
    OrganizationId,
    VideoId,
    new_id,
    utcnow,
)


class JobStatus:
    __slots__ = ("value",)

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

    ALLOWED = frozenset({QUEUED, RUNNING, COMPLETED, FAILED})
    TERMINAL = frozenset({COMPLETED, FAILED})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown job status: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"JobStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JobStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)

    @property
    def is_terminal(self) -> bool:
        return self.value in self.TERMINAL


@dataclass(slots=True)
class ProcessingJob:
    organization_id: OrganizationId
    job_type: str
    video_id: VideoId
    id: JobId = field(default_factory=lambda: JobId(new_id()))
    status: JobStatus = field(default_factory=lambda: JobStatus(JobStatus.QUEUED))
    attempt: int = 0
    max_attempts: int = 3
    progress: float = 0.0
    error: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.job_type.strip():
            raise ValueError("Processing job job_type must not be empty.")
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")
        if not (0.0 <= self.progress <= 100.0):
            raise ValueError("progress must be between 0 and 100.")

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def can_retry(self) -> bool:
        return self.attempt < self.max_attempts

    def start(self) -> None:
        if self.status.value == JobStatus.RUNNING:
            return
        if self.status.value not in {JobStatus.QUEUED, JobStatus.FAILED}:
            raise ValueError(f"Cannot start a {self.status} job.")
        self.status = JobStatus(JobStatus.RUNNING)
        self.attempt += 1
        self.started_at = utcnow()
        self.completed_at = None
        self.updated_at = utcnow()

    def report_progress(self, percent: float) -> None:
        if not (0.0 <= percent <= 100.0):
            raise ValueError("progress must be between 0 and 100.")
        if self.is_terminal:
            raise ValueError("Cannot report progress on a finished job.")
        self.progress = percent
        self.updated_at = utcnow()

    def complete(self) -> None:
        self.status = JobStatus(JobStatus.COMPLETED)
        self.progress = 100.0
        self.error = None
        self.completed_at = utcnow()
        self.updated_at = utcnow()

    def fail(self, message: str) -> None:
        if not message.strip():
            raise ValueError("A failure message is required.")
        self.status = JobStatus(JobStatus.FAILED)
        self.error = message
        self.completed_at = utcnow()
        self.updated_at = utcnow()

    def requeue(self) -> None:
        if self.status.value != JobStatus.FAILED:
            raise ValueError(f"Cannot requeue a {self.status} job.")
        if not self.can_retry:
            raise ValueError("Job has exhausted its retry budget.")
        self.status = JobStatus(JobStatus.QUEUED)
        self.updated_at = utcnow()
