"""Videos: uploaded source media and its ingestion lifecycle.

The upload state machine is domain code, not a database enum, because it encodes
when an upload becomes eligible for processing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import (
    MatchId,
    OrganizationId,
    VideoId,
    VideoSpec,
    new_id,
    utcnow,
)


class VideoStatus:
    """Lifecycle state of a video asset.

    A constrained string rather than a database enum: adding a state (for
    example ' 'quarantined' ' or ' 'archived' ') must not require a migration that
    rewrites a PostgreSQL type.

    The upload half of the lifecycle is ' 'pending' ' → ' 'uploading' ' → ' 'uploaded' ',
    with ' 'failed' ' reachable when the transfer never lands. The states after it
    describe ingestion and analysis of bytes that are already in storage.
    """

    __slots__ = ("value",)

    PENDING = "pending"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    STORED = "stored"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"

    ALLOWED = frozenset({PENDING, UPLOADING, UPLOADED, STORED, PROCESSING, READY, FAILED})

    #: States in which no object exists yet, so the row may be re-uploaded.
    AWAITING_UPLOAD = frozenset({PENDING, UPLOADING, FAILED})

    #: States from which a new analysis run may legitimately be scheduled.
    ANALYSABLE = frozenset({STORED, READY})

    #: States whose object exists and is valid, so processing may be requested.
    #: 'uploaded' is included because the completion step has already verified the
    #: object against storage; 'stored' and 'ready' allow a re-process.
    PROCESSABLE = frozenset({UPLOADED, STORED, READY})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown video status: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"VideoStatus({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, VideoStatus):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(slots=True)
class Video:
    """An uploaded recording.

    The binary itself never lives in PostgreSQL. ' 'storage_key' ' is an opaque
    pointer into object storage; the database stores metadata and lifecycle
    only. Swapping local disk for S3 must not touch this record's shape.
    """

    organization_id: OrganizationId
    original_filename: str
    storage_key: str
    id: VideoId = field(default_factory=lambda: VideoId(new_id()))
    match_id: MatchId | None = None
    status: VideoStatus = field(default_factory=lambda: VideoStatus(VideoStatus.PENDING))
    content_type: str | None = None
    size_bytes: int | None = None
    checksum: str | None = None
    spec: VideoSpec = field(default_factory=VideoSpec)
    # Free-form ingestion metadata: codec quirks, probe output, camera notes.
    # Genuinely schema-less, so JSONB is the right home for it (see
    # docs/architecture/database.md).
    metadata: dict[str, object] = field(default_factory=dict)
    failure_reason: str | None = None
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if not self.original_filename.strip():
            raise ValueError("Video original_filename must not be empty.")
        if not self.storage_key.strip():
            raise ValueError("Video storage_key must not be empty.")
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes cannot be negative.")

    @property
    def is_analysable(self) -> bool:
        return self.status.value in VideoStatus.ANALYSABLE

    @property
    def is_awaiting_upload(self) -> bool:
        return self.status.value in VideoStatus.AWAITING_UPLOAD

    @property
    def is_processable(self) -> bool:
        return self.status.value in VideoStatus.PROCESSABLE

    # Guarded so that an illegal transition (e.g. scheduling work for a video
    # whose upload never completed) fails here rather than inside a worker.

    def mark_uploading(self) -> None:
        """Record that a client has been authorised to send bytes.

        Only valid before the bytes land: re-authorising a video whose object is
        already in storage would let a second upload overwrite the first without
        the database noticing.
        """
        if not self.is_awaiting_upload:
            raise ValueError(f"Cannot start an upload for a {self.status} video.")
        self.status = VideoStatus(VideoStatus.UPLOADING)
        self.failure_reason = None
        self.updated_at = utcnow()

    def mark_uploaded(self, *, size_bytes: int, content_type: str | None = None) -> None:
        """Record a verified, complete upload.

        The transition is guarded rather than silent so that a second completion
        cannot rewrite what the first recorded; the caller decides whether a
        repeated call is a no-op or a conflict.
        """
        if not self.is_awaiting_upload:
            raise ValueError(f"Cannot mark a {self.status} video as uploaded.")
        if size_bytes < 0:
            raise ValueError("size_bytes cannot be negative.")
        self.size_bytes = size_bytes
        self.content_type = content_type or self.content_type
        self.status = VideoStatus(VideoStatus.UPLOADED)
        self.failure_reason = None
        self.updated_at = utcnow()

    def mark_stored(self, *, spec: VideoSpec | None = None) -> None:
        if self.status.value not in {VideoStatus.UPLOADED, VideoStatus.STORED, VideoStatus.FAILED}:
            raise ValueError(f"Cannot mark a {self.status} video as stored.")
        if spec is not None:
            self.spec = spec
        self.status = VideoStatus(VideoStatus.STORED)
        self.failure_reason = None
        self.updated_at = utcnow()

    def mark_processing(self) -> None:
        if not self.is_processable and self.status.value != VideoStatus.PROCESSING:
            raise ValueError(f"Cannot start processing a {self.status} video.")
        self.status = VideoStatus(VideoStatus.PROCESSING)
        self.failure_reason = None
        self.updated_at = utcnow()

    def mark_ready(self) -> None:
        if self.status.value not in {VideoStatus.PROCESSING, VideoStatus.READY}:
            raise ValueError(f"Cannot mark a {self.status} video as processed.")
        self.status = VideoStatus(VideoStatus.READY)
        self.failure_reason = None
        self.updated_at = utcnow()

    def mark_failed(self, reason: str) -> None:
        if not reason.strip():
            raise ValueError("A failure reason is required.")
        self.status = VideoStatus(VideoStatus.FAILED)
        self.failure_reason = reason
        self.updated_at = utcnow()

    def attach_to_match(self, match_id: MatchId) -> None:
        self.match_id = match_id
        self.updated_at = utcnow()

    def record_probe(self, spec: VideoSpec, *, checksum: str | None = None) -> None:
        """Persist technical metadata returned by media probing.

        Called by the ingestion step, not by the HTTP request that received the
        bytes.
        """
        self.spec = spec
        if checksum is not None:
            self.checksum = checksum
        self.updated_at = utcnow()
