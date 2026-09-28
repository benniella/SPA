"""Domain entities for player and ball trajectories."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.domain.shared import (
    AnalysisRunId,
    OrganizationId,
    PitchCoordinate,
    TrackingDatasetId,
    TrackObservationId,
    VideoId,
    new_id,
    utcnow,
)


class TrackObjectType:
    """What a tracked object is."""

    __slots__ = ("value",)

    PLAYER = "player"
    REFEREE = "referee"
    BALL = "ball"
    UNKNOWN = "unknown"

    ALLOWED = frozenset({PLAYER, REFEREE, BALL, UNKNOWN})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown tracked object type: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"TrackObjectType({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TrackObjectType):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class TrackObservation:
    """One tracked object detected in one frame."""

    frame_index: int
    timestamp_seconds: float
    object_type: TrackObjectType
    track_id: int
    confidence: float
    pitch_position: PitchCoordinate | None = None
    pixel_bbox: tuple[float, float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index cannot be negative.")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds cannot be negative.")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class TrackedObservation:
    """One tracked object in one sampled frame, in source-image pixel space.

    Distinct from ' 'TrackObservation' ': that carries an optional pitch-space
    position and a sport object type (player, referee, ball). The tracking stage
    knows only that a detector found an object and a tracker gave it an identity,
    so this type deliberately has no sport vocabulary. Coordinates are pixels — the
    camera calibration that would map them to the pitch does not exist yet.
    """

    track_id: int
    class_id: int
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    frame_index: int
    timestamp_seconds: float

    def __post_init__(self) -> None:
        if self.frame_index < 0:
            raise ValueError("frame_index cannot be negative.")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds cannot be negative.")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1.")
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("A bounding box requires x2 >= x1 and y2 >= y1.")


@dataclass(frozen=True, slots=True)
class TrackRecord:
    """A persisted 'TrackedObservation' ' with its identifiers and storage time.

    The row a read path returns: the observation plus the run, video and dataset
    it belongs to, so a caller can authorize it without a second query.
    """

    id: TrackObservationId
    organization_id: OrganizationId
    video_id: VideoId
    analysis_run_id: AnalysisRunId
    observation: TrackedObservation
    created_at: datetime


@dataclass(slots=True)
class TrackingDataset:
    """Versioned trajectory output from one tracking-stage execution."""

    organization_id: OrganizationId
    video_id: VideoId
    analysis_run_id: AnalysisRunId
    id: TrackingDatasetId = field(default_factory=lambda: TrackingDatasetId(new_id()))
    frame_rate: float | None = None
    frame_count: int | None = None
    object_count: int | None = None
    storage_key: str | None = None
    provenance: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        if self.frame_count is not None and self.frame_count < 0:
            raise ValueError("frame_count cannot be negative.")
        if self.object_count is not None and self.object_count < 0:
            raise ValueError("object_count cannot be negative.")


@dataclass(frozen=True, slots=True)
class TrackSegment:
    """A contiguous slice of one object's trajectory."""

    track_id: int
    start_seconds: float
    end_seconds: float
    object_type: TrackObjectType

    def __post_init__(self) -> None:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("end_seconds must be greater than start_seconds.")

    @property
    def duration_seconds(self) -> float:
        return self.end_seconds - self.start_seconds
