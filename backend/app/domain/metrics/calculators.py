from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence

from app.domain.metrics import movement
from app.domain.metrics.types import (
    AnalysisMetrics,
    MetricName,
    MetricSpace,
    MetricUnit,
    MetricValue,
    TrackMetrics,
    TrackObservationPoint,
)
from app.domain.shared import AnalysisRunId, OrganizationId


class MetricCalculator:
    """Derives one track's metrics from its observations.

    Bounded on purpose: it accepts an iterable, consumes it once, and holds only
    the observations for a single track. A match's observations are never all in
    memory at the same time.
    """

    def __init__(self, *, max_gap_seconds: float) -> None:
        if max_gap_seconds <= 0:
            raise ValueError("max_gap_seconds must be positive.")
        self._max_gap_seconds = max_gap_seconds

    def calculate(
        self, track_id: int, observations: Iterable[TrackObservationPoint]
    ) -> TrackMetrics:
        points = movement.canonical_order(observations)
        return TrackMetrics(
            track_id=track_id,
            space=MetricSpace.SOURCE,
            values=(
                _observation_count(points),
                _duration(points),
                _coverage(points),
                movement.displacement(points, max_gap_seconds=self._max_gap_seconds),
                movement.average_speed(points, max_gap_seconds=self._max_gap_seconds),
                movement.peak_speed(points, max_gap_seconds=self._max_gap_seconds),
                movement.average_acceleration(points, max_gap_seconds=self._max_gap_seconds),
                movement.peak_acceleration(points, max_gap_seconds=self._max_gap_seconds),
                _mean_confidence(points),
                _extreme_confidence(points, MetricName.MIN_CONFIDENCE, min),
                _extreme_confidence(points, MetricName.MAX_CONFIDENCE, max),
            ),
        )


def build_analysis_metrics(
    *,
    analysis_run_id: AnalysisRunId,
    organization_id: OrganizationId,
    track_metrics: Sequence[TrackMetrics],
) -> AnalysisMetrics:
    return AnalysisMetrics(
        analysis_run_id=analysis_run_id,
        organization_id=organization_id,
        space=MetricSpace.SOURCE,
        tracks=tuple(track_metrics),
    )


def _observation_count(points: list[TrackObservationPoint]) -> MetricValue:
    return MetricValue.available(
        MetricName.OBSERVATION_COUNT,
        MetricUnit.COUNT,
        float(len(points)),
        sample_count=len(points),
    )


def _duration(points: list[TrackObservationPoint]) -> MetricValue:
    if len(points) < movement.MIN_MOVEMENT_OBSERVATIONS:
        return MetricValue.unavailable(
            MetricName.DURATION, MetricUnit.SECONDS, sample_count=len(points)
        )
    span = points[-1].timestamp_seconds - points[0].timestamp_seconds
    return MetricValue.available(
        MetricName.DURATION, MetricUnit.SECONDS, span, sample_count=len(points)
    )


def _coverage(points: list[TrackObservationPoint]) -> MetricValue:
    """The share of sampled frames this track has an observation in.

    Measured across the track's own frame span, so it reflects tracking
    continuity: a track with a large hole has low coverage.
    """
    if len(points) < movement.MIN_MOVEMENT_OBSERVATIONS:
        return MetricValue.unavailable(
            MetricName.COVERAGE, MetricUnit.COUNT, sample_count=len(points)
        )
    span = points[-1].frame_index - points[0].frame_index + 1
    return MetricValue.available(
        MetricName.COVERAGE, MetricUnit.COUNT, len(points) / span, sample_count=span
    )


def _mean_confidence(points: list[TrackObservationPoint]) -> MetricValue:
    if not points:
        return MetricValue.unavailable(MetricName.MEAN_CONFIDENCE, MetricUnit.COUNT)
    confidences = [point.confidence for point in points]
    return MetricValue.available(
        MetricName.MEAN_CONFIDENCE,
        MetricUnit.COUNT,
        sum(confidences) / len(confidences),
        sample_count=len(confidences),
    )


def _extreme_confidence(
    points: list[TrackObservationPoint],
    name: MetricName,
    reducer: Callable[[list[float]], float],
) -> MetricValue:
    if not points:
        return MetricValue.unavailable(name, MetricUnit.COUNT)
    confidences = [point.confidence for point in points]
    return MetricValue.available(
        name, MetricUnit.COUNT, reducer(confidences), sample_count=len(confidences)
    )
