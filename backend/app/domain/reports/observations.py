from __future__ import annotations

from dataclasses import dataclass

from app.domain.metrics.types import MetricName, MetricSpace, MetricUnit, TrackMetrics
from app.domain.reports.content import DataObservation, ObservationType

#: Floating-point values are compared after rounding to this many places, so two
#: tracks whose speeds differ only below the precision the report states are
#: treated as tied rather than being ranked by an invisible difference.
PRECISION = 6


@dataclass(frozen=True, slots=True)
class ObservationRule:
    """One mechanical, testable statement about a metric across a run.

    The rule emits nothing unless every candidate carries an available value, so
    an observation is never built from a metric that could not be measured.
    """

    type: ObservationType
    metric_name: MetricName
    label: str

    def evaluate(self, tracks: tuple[TrackMetrics, ...]) -> DataObservation | None:
        candidates = [
            (track.track_id, value)
            for track in tracks
            if (value := _available_value(track, self.metric_name)) is not None
        ]
        if not candidates:
            return None

        highest = max(round(value, PRECISION) for _, value in candidates)
        leaders = sorted(
            track_id for track_id, value in candidates if round(value, PRECISION) == highest
        )

        unit = _unit_of(tracks, self.metric_name)
        return DataObservation(
            type=self.type,
            track_ids=tuple(leaders),
            metric_name=self.metric_name,
            unit=unit,
            space=MetricSpace.SOURCE,
            value=highest,
            message=_message(self.label, leaders, highest, unit),
        )


def _unit_of(tracks: tuple[TrackMetrics, ...], name: MetricName) -> MetricUnit:
    for track in tracks:
        value = track.value_for(name)
        if value is not None:
            return value.unit
    return MetricUnit.COUNT


def _available_value(track: TrackMetrics, name: MetricName) -> float | None:
    value = track.value_for(name)
    if value is None or not value.is_available or value.value is None:
        return None
    return value.value


def _message(label: str, leaders: list[int], value: float, unit: MetricUnit) -> str:
    tracks = _track_phrase(leaders)
    measured = f"{_format(value)}{_suffix(unit)}"
    return f"{tracks} {_verb(leaders)} the highest observed {label} in this analysis: {measured}."


def _track_phrase(track_ids: list[int]) -> str:
    if len(track_ids) == 1:
        return f"Track {track_ids[0]}"
    joined = ", ".join(str(track_id) for track_id in track_ids[:-1])
    return f"Tracks {joined} and {track_ids[-1]}"


def _verb(track_ids: list[int]) -> str:
    return "has" if len(track_ids) == 1 else "share"


def _format(value: float) -> str:
    if value.is_integer():
        return f"{value:,.0f}"
    return f"{value:,.2f}"


def _suffix(unit: MetricUnit) -> str:
    return {
        MetricUnit.COUNT: "",
        MetricUnit.SECONDS: " s",
        MetricUnit.PIXELS: " px",
        MetricUnit.PIXELS_PER_SECOND: " px/s",
        MetricUnit.PIXELS_PER_SECOND_SQUARED: " px/s²",
    }[unit]


#: Evaluated in this order, so the observation list is deterministic and reads
#: from the most to the least prominent measured quantity.
OBSERVATION_RULES: tuple[ObservationRule, ...] = (
    ObservationRule(
        ObservationType.HIGHEST_OBSERVATION_COUNT, MetricName.OBSERVATION_COUNT, "observation count"
    ),
    ObservationRule(ObservationType.LONGEST_DURATION, MetricName.DURATION, "duration"),
    ObservationRule(ObservationType.HIGHEST_DISPLACEMENT, MetricName.DISPLACEMENT, "displacement"),
    ObservationRule(
        ObservationType.HIGHEST_AVERAGE_SPEED, MetricName.AVERAGE_SPEED, "average speed"
    ),
    ObservationRule(ObservationType.HIGHEST_PEAK_SPEED, MetricName.PEAK_SPEED, "peak speed"),
    ObservationRule(
        ObservationType.HIGHEST_PEAK_ACCELERATION,
        MetricName.PEAK_ACCELERATION,
        "peak acceleration",
    ),
    ObservationRule(ObservationType.HIGHEST_COVERAGE, MetricName.COVERAGE, "coverage"),
)


def derive_observations(tracks: tuple[TrackMetrics, ...]) -> tuple[DataObservation, ...]:
    """Derive the run's factual observations from its existing metrics.

    Nothing here introduces a metric, scores a track or ranks one against
    another: each rule reports the maximum of a value that is already persisted,
    and names every track that ties for it.
    """
    return tuple(
        observation for rule in OBSERVATION_RULES if (observation := rule.evaluate(tracks))
    )
