"""The metric vocabulary.

The metrics engine derives quantitative facts from tracking observations and
knows nothing else: not a detector, not a tracker, not a database session, not a
sport. Coordinates are source-image pixels because SPA has no spatial
calibration yet, and a physical unit is therefore never produced here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from app.domain.shared import AnalysisRunId, OrganizationId, TrackMetricId, new_id, utcnow


class MetricSpace(StrEnum):
    """Which coordinate space a metric's numbers are expressed in.

    The distinction prevents pixels from being read as metres. Calibrated
    values are represented separately from source-image coordinates.
    """

    SOURCE = "source"
    CALIBRATED = "calibrated"


class MetricUnit(StrEnum):
    COUNT = "count"
    SECONDS = "seconds"
    PIXELS = "pixels"
    PIXELS_PER_SECOND = "pixels_per_second"
    PIXELS_PER_SECOND_SQUARED = "pixels_per_second_squared"


class MetricName(StrEnum):
    """The metric catalogue.

    Names are application-controlled: a client can never introduce one, which is
    why they are an enum rather than free strings.
    """

    OBSERVATION_COUNT = "observation_count"
    DURATION = "duration"
    COVERAGE = "coverage"
    DISPLACEMENT = "displacement"
    AVERAGE_SPEED = "average_speed"
    PEAK_SPEED = "peak_speed"
    AVERAGE_ACCELERATION = "average_acceleration"
    PEAK_ACCELERATION = "peak_acceleration"
    MEAN_CONFIDENCE = "mean_confidence"
    MIN_CONFIDENCE = "min_confidence"
    MAX_CONFIDENCE = "max_confidence"


class MetricAvailability(StrEnum):
    """Why a metric does or does not carry a value.

    ``UNAVAILABLE`` is a first-class outcome, not an error: a track with one
    observation genuinely has no speed, and reporting ``0`` would be a claim.
    """

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class TrackObservationPoint:
    """One tracked object's position at one instant, in source-image pixels.

    The metrics engine's only input type. It is deliberately not the persistence
    row and not the detector's output, so replacing either does not touch a
    calculator.
    """

    track_id: int
    frame_index: int
    timestamp_seconds: float
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def center_x(self) -> float:
        return (self.x1 + self.x2) / 2.0

    @property
    def center_y(self) -> float:
        return (self.y1 + self.y2) / 2.0


@dataclass(frozen=True, slots=True)
class MetricValue:
    """A metric's outcome, carrying its unit and whether it exists at all."""

    name: MetricName
    availability: MetricAvailability
    unit: MetricUnit
    value: float | None = None
    sample_count: int = 0

    @property
    def is_available(self) -> bool:
        return self.availability is MetricAvailability.AVAILABLE and self.value is not None

    @classmethod
    def available(
        cls,
        name: MetricName,
        unit: MetricUnit,
        value: float,
        *,
        sample_count: int,
    ) -> MetricValue:
        return cls(
            name=name,
            availability=MetricAvailability.AVAILABLE,
            unit=unit,
            value=value,
            sample_count=sample_count,
        )

    @classmethod
    def unavailable(
        cls,
        name: MetricName,
        unit: MetricUnit,
        *,
        sample_count: int = 0,
    ) -> MetricValue:
        return cls(
            name=name,
            availability=MetricAvailability.UNAVAILABLE,
            unit=unit,
            value=None,
            sample_count=sample_count,
        )


@dataclass(frozen=True, slots=True)
class TrackMetrics:
    """Every metric derived for one tracked object."""

    track_id: int
    space: MetricSpace
    values: tuple[MetricValue, ...]

    def value_for(self, name: MetricName) -> MetricValue | None:
        for value in self.values:
            if value.name is name:
                return value
        return None


@dataclass(frozen=True, slots=True)
class TrackMetricRecord:
    """One persisted derived metric for one track.

    The storage counterpart of ' 'MetricValue' ': it carries the run and
    organization it belongs to so a read path can authorize without a join.
    """

    organization_id: OrganizationId
    analysis_run_id: AnalysisRunId
    track_id: int
    value: MetricValue
    space: MetricSpace = MetricSpace.SOURCE
    definition_version: str = "v1"
    id: TrackMetricId = field(default_factory=lambda: TrackMetricId(new_id()))
    created_at: datetime = field(default_factory=utcnow)


@dataclass(frozen=True, slots=True)
class AnalysisMetrics:
    """A run's derived metrics, grouped by track.

    The shape the API and any later visualisation layer read. It is a small,
    explicit structure rather than a nested dictionary so that a future
    calibrated or sport-specific metric can be added without changing consumers.
    """

    analysis_run_id: AnalysisRunId
    organization_id: OrganizationId
    space: MetricSpace
    tracks: tuple[TrackMetrics, ...]
    definition_version: str = "v1"
    generated_at: datetime = field(default_factory=utcnow)
