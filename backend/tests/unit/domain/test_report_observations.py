from __future__ import annotations

from app.domain.metrics.types import (
    MetricName,
    MetricSpace,
    MetricUnit,
    MetricValue,
    TrackMetrics,
)
from app.domain.reports.observations import derive_observations


def track(track_id: int, *metrics: MetricValue) -> TrackMetrics:
    return TrackMetrics(track_id=track_id, space=MetricSpace.SOURCE, values=tuple(metrics))


def measured(name: MetricName, value: float, unit: MetricUnit = MetricUnit.COUNT) -> MetricValue:
    return MetricValue.available(name, unit, value, sample_count=4)


def unmeasured(name: MetricName, unit: MetricUnit = MetricUnit.COUNT) -> MetricValue:
    return MetricValue.unavailable(name, unit)


class TestHighestValueRule:
    def test_names_the_track_with_the_highest_peak_speed(self) -> None:
        tracks = (
            track(1, measured(MetricName.PEAK_SPEED, 20.0, MetricUnit.PIXELS_PER_SECOND)),
            track(2, measured(MetricName.PEAK_SPEED, 51.2, MetricUnit.PIXELS_PER_SECOND)),
            track(3, measured(MetricName.PEAK_SPEED, 24.9, MetricUnit.PIXELS_PER_SECOND)),
        )

        observation = _find(derive_observations(tracks), "highest_peak_speed")

        assert observation is not None
        assert observation.track_ids == (2,)
        assert observation.value == 51.2
        assert observation.unit is MetricUnit.PIXELS_PER_SECOND
        assert observation.space is MetricSpace.SOURCE
        assert "Track 2" in observation.message
        assert "51.20 px/s" in observation.message

    def test_a_tie_names_every_track_that_shares_the_value(self) -> None:
        tracks = (
            track(3, measured(MetricName.PEAK_SPEED, 42.1, MetricUnit.PIXELS_PER_SECOND)),
            track(7, measured(MetricName.PEAK_SPEED, 42.1, MetricUnit.PIXELS_PER_SECOND)),
        )

        observation = _find(derive_observations(tracks), "highest_peak_speed")

        assert observation is not None
        assert observation.track_ids == (3, 7)
        assert "Tracks 3 and 7 share" in observation.message

    def test_a_value_only_below_the_reported_precision_is_not_a_tie(self) -> None:
        tracks = (
            track(1, measured(MetricName.PEAK_SPEED, 42.1234561, MetricUnit.PIXELS_PER_SECOND)),
            track(2, measured(MetricName.PEAK_SPEED, 42.1234569, MetricUnit.PIXELS_PER_SECOND)),
        )

        observation = _find(derive_observations(tracks), "highest_peak_speed")

        assert observation is not None
        assert len(observation.track_ids) == 1

    def test_an_unavailable_metric_produces_no_observation(self) -> None:
        tracks = (track(1, unmeasured(MetricName.PEAK_SPEED)),)

        assert _find(derive_observations(tracks), "highest_peak_speed") is None

    def test_a_missing_metric_produces_no_observation(self) -> None:
        tracks = (track(1, measured(MetricName.COVERAGE, 0.91)),)

        assert _find(derive_observations(tracks), "highest_peak_speed") is None

    def test_available_and_unavailable_tracks_rank_by_the_available_values(self) -> None:
        tracks = (
            track(1, unmeasured(MetricName.DISPLACEMENT, MetricUnit.PIXELS)),
            track(2, measured(MetricName.DISPLACEMENT, 300.0, MetricUnit.PIXELS)),
        )

        observation = _find(derive_observations(tracks), "highest_displacement")

        assert observation is not None
        assert observation.track_ids == (2,)


class TestObservationOrdering:
    def test_observations_are_emitted_in_a_stable_order(self) -> None:
        tracks = (
            track(
                1,
                measured(MetricName.OBSERVATION_COUNT, 120.0),
                measured(MetricName.DURATION, 47.0, MetricUnit.SECONDS),
                measured(MetricName.COVERAGE, 0.91),
            ),
            track(
                2,
                measured(MetricName.OBSERVATION_COUNT, 60.0),
                measured(MetricName.DURATION, 30.0, MetricUnit.SECONDS),
                measured(MetricName.COVERAGE, 0.5),
            ),
        )

        first = derive_observations(tracks)
        second = derive_observations(tracks)

        assert [observation.type for observation in first] == [
            observation.type for observation in second
        ]
        assert [observation.message for observation in first] == [
            observation.message for observation in second
        ]

    def test_no_new_metric_is_introduced(self) -> None:
        tracks = (track(1, measured(MetricName.OBSERVATION_COUNT, 5.0)),)

        cat = set(MetricName)
        for observation in derive_observations(tracks):
            assert observation.metric_name in cat


def _find(observations: tuple, type_name: str) -> object | None:
    for observation in observations:
        if str(observation.type) == type_name:
            return observation
    return None
