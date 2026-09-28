"""Deterministic metric engine tests.

Every fixture is a small handcrafted set of observations with a known answer, so
a change in a calculator's behaviour fails here rather than in a report a coach
reads. Nothing in this module needs a database, a model or a video.
"""

from __future__ import annotations

import math

import pytest

from app.domain.metrics.calculators import MetricCalculator
from app.domain.metrics.types import (
    MetricAvailability,
    MetricName,
    MetricSpace,
    MetricUnit,
    TrackObservationPoint,
)

MAX_GAP = 2.0


def point(
    *,
    track_id: int = 1,
    frame_index: int,
    timestamp_seconds: float,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    confidence: float = 0.9,
) -> TrackObservationPoint:
    return TrackObservationPoint(
        track_id=track_id,
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        x1=x1,
        y1=y1,
        x2=x2,
        y2=y2,
        confidence=confidence,
    )


def stationary(*, count: int = 4, confidence: float = 0.8) -> list[TrackObservationPoint]:
    return [
        point(
            frame_index=index,
            timestamp_seconds=float(index) * 0.5,
            x1=10.0,
            y1=10.0,
            x2=30.0,
            y2=50.0,
            confidence=confidence,
        )
        for index in range(count)
    ]


def constant_movement(*, step: float = 10.0, count: int = 4) -> list[TrackObservationPoint]:
    """A box whose centre advances by 'step' pixels every 0.5 s."""
    return [
        point(
            frame_index=index,
            timestamp_seconds=float(index) * 0.5,
            x1=10.0 + index * step,
            y1=10.0,
            x2=30.0 + index * step,
            y2=50.0,
        )
        for index in range(count)
    ]


class TestStationaryTrack:
    def test_reports_zero_displacement_and_speed(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, stationary())

        assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(0.0)
        assert metrics.value_for(MetricName.AVERAGE_SPEED).value == pytest.approx(0.0)
        assert metrics.value_for(MetricName.PEAK_SPEED).value == pytest.approx(0.0)
        assert metrics.value_for(MetricName.AVERAGE_ACCELERATION).value == pytest.approx(0.0)

    def test_reports_its_units_and_source_space(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, stationary())

        assert metrics.space is MetricSpace.SOURCE
        assert metrics.value_for(MetricName.DISPLACEMENT).unit is MetricUnit.PIXELS
        assert metrics.value_for(MetricName.AVERAGE_SPEED).unit is MetricUnit.PIXELS_PER_SECOND


class TestConstantMovement:
    def test_displacement_is_the_sum_of_the_steps(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(
            1, constant_movement(step=10.0, count=4)
        )

        # Three intervals of 10 px each.
        assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(30.0)
        assert metrics.value_for(MetricName.DISPLACEMENT).sample_count == 3

    def test_speed_is_displacement_over_elapsed_time(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(
            1, constant_movement(step=10.0, count=4)
        )

        # 10 px per 0.5 s interval → 20 px/s, and constant, so average == peak.
        assert metrics.value_for(MetricName.AVERAGE_SPEED).value == pytest.approx(20.0)
        assert metrics.value_for(MetricName.PEAK_SPEED).value == pytest.approx(20.0)

    def test_duration_spans_first_to_last_observation(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(
            1, constant_movement(step=10.0, count=4)
        )

        assert metrics.value_for(MetricName.DURATION).value == pytest.approx(1.5)
        assert metrics.value_for(MetricName.DURATION).unit is MetricUnit.SECONDS

    def test_observation_count_and_coverage(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(
            1, constant_movement(step=10.0, count=4)
        )

        assert metrics.value_for(MetricName.OBSERVATION_COUNT).value == pytest.approx(4.0)
        assert metrics.value_for(MetricName.COVERAGE).value == pytest.approx(1.0)


class TestVariableMovement:
    def test_peak_speed_exceeds_average_speed(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=1, timestamp_seconds=1.0, x1=10, y1=0, x2=10, y2=0),
            point(frame_index=2, timestamp_seconds=2.0, x1=60, y1=0, x2=60, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        # Interval speeds: 10 px/s then 50 px/s.
        assert metrics.value_for(MetricName.AVERAGE_SPEED).value == pytest.approx(30.0)
        assert metrics.value_for(MetricName.PEAK_SPEED).value == pytest.approx(50.0)


class TestAcceleration:
    def test_acceleration_is_change_in_velocity_over_time(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=1, timestamp_seconds=1.0, x1=10, y1=0, x2=10, y2=0),
            point(frame_index=2, timestamp_seconds=2.0, x1=30, y1=0, x2=30, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        # 10 px/s → 20 px/s across a 1 s mid-interval step.
        assert metrics.value_for(MetricName.AVERAGE_ACCELERATION).value == pytest.approx(10.0)
        assert (
            metrics.value_for(MetricName.AVERAGE_ACCELERATION).unit
            is MetricUnit.PIXELS_PER_SECOND_SQUARED
        )

    def test_two_observations_yield_no_acceleration(self) -> None:
        observations = constant_movement(count=2)
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        assert metrics.value_for(MetricName.AVERAGE_ACCELERATION).availability is (
            MetricAvailability.UNAVAILABLE
        )
        assert metrics.value_for(MetricName.AVERAGE_ACCELERATION).value is None


class TestGaps:
    def test_a_large_gap_does_not_create_movement(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            # Ten seconds and 500 px later: a re-appearance, not a sprint.
            point(frame_index=1, timestamp_seconds=10.0, x1=500, y1=0, x2=500, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        assert metrics.value_for(MetricName.DISPLACEMENT).availability is (
            MetricAvailability.UNAVAILABLE
        )
        assert metrics.value_for(MetricName.PEAK_SPEED).value is None

    def test_a_gap_is_excluded_but_surrounding_movement_is_kept(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=1, timestamp_seconds=0.5, x1=10, y1=0, x2=10, y2=0),
            point(frame_index=2, timestamp_seconds=30.0, x1=900, y1=0, x2=900, y2=0),
            point(frame_index=3, timestamp_seconds=30.5, x1=920, y1=0, x2=920, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(30.0)
        assert metrics.value_for(MetricName.DISPLACEMENT).sample_count == 2

    def test_coverage_reflects_a_tracking_hole(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=4, timestamp_seconds=0.5, x1=10, y1=0, x2=10, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        # Two observations across five frames.
        assert metrics.value_for(MetricName.COVERAGE).value == pytest.approx(0.4)


class TestInvalidObservations:
    def test_a_repeated_frame_is_not_movement(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=0, timestamp_seconds=0.0, x1=90, y1=0, x2=90, y2=0),
            point(frame_index=1, timestamp_seconds=0.5, x1=100, y1=0, x2=100, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        # Only the 0 → 1 step counts.
        assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(10.0)
        assert metrics.value_for(MetricName.DISPLACEMENT).sample_count == 1

    def test_a_backwards_timestamp_is_ignored(self) -> None:
        observations = [
            point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
            point(frame_index=1, timestamp_seconds=0.0, x1=100, y1=0, x2=100, y2=0),
            point(frame_index=2, timestamp_seconds=0.5, x1=110, y1=0, x2=110, y2=0),
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(10.0)
        assert metrics.value_for(MetricName.DISPLACEMENT).sample_count == 1

    def test_ordering_is_canonical_regardless_of_input_order(self) -> None:
        forward = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, constant_movement(count=4))
        shuffled = list(reversed(constant_movement(count=4)))
        backward = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, shuffled)

        assert forward == backward


class TestInsufficientObservations:
    def test_a_single_observation_yields_no_movement_metrics(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, stationary(count=1))

        for name in (
            MetricName.DISPLACEMENT,
            MetricName.AVERAGE_SPEED,
            MetricName.PEAK_SPEED,
            MetricName.DURATION,
        ):
            value = metrics.value_for(name)
            assert value.availability is MetricAvailability.UNAVAILABLE
            assert value.value is None

    def test_a_single_observation_still_reports_its_count_and_confidence(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(
            1, stationary(count=1, confidence=0.42)
        )

        assert metrics.value_for(MetricName.OBSERVATION_COUNT).value == pytest.approx(1.0)
        assert metrics.value_for(MetricName.MEAN_CONFIDENCE).value == pytest.approx(0.42)

    def test_no_observations_is_not_an_error(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, [])

        assert metrics.value_for(MetricName.OBSERVATION_COUNT).value == pytest.approx(0.0)
        assert metrics.value_for(MetricName.DISPLACEMENT).value is None


class TestConfidenceSummary:
    def test_reports_mean_minimum_and_maximum(self) -> None:
        observations = [
            point(
                frame_index=index,
                timestamp_seconds=float(index) * 0.5,
                x1=0,
                y1=0,
                x2=0,
                y2=0,
                confidence=confidence,
            )
            for index, confidence in enumerate((0.2, 0.5, 0.9))
        ]
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

        assert metrics.value_for(MetricName.MEAN_CONFIDENCE).value == pytest.approx(
            (0.2 + 0.5 + 0.9) / 3
        )
        assert metrics.value_for(MetricName.MIN_CONFIDENCE).value == pytest.approx(0.2)
        assert metrics.value_for(MetricName.MAX_CONFIDENCE).value == pytest.approx(0.9)


class TestTrackIsolation:
    def test_each_track_is_calculated_independently(self) -> None:
        calculator = MetricCalculator(max_gap_seconds=MAX_GAP)
        first = calculator.calculate(1, stationary())
        second = calculator.calculate(2, constant_movement(step=25.0, count=3))

        assert first.track_id == 1
        assert first.value_for(MetricName.DISPLACEMENT).value == pytest.approx(0.0)
        assert second.track_id == 2
        assert second.value_for(MetricName.DISPLACEMENT).value == pytest.approx(50.0)


class TestCalculatorContract:
    def test_a_non_positive_gap_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            MetricCalculator(max_gap_seconds=0.0)

    def test_units_are_explicit_on_every_movement_metric(self) -> None:
        metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, constant_movement())

        assert metrics.value_for(MetricName.DISPLACEMENT).unit == MetricUnit.PIXELS
        assert metrics.value_for(MetricName.AVERAGE_SPEED).unit == MetricUnit.PIXELS_PER_SECOND
        assert (
            metrics.value_for(MetricName.PEAK_ACCELERATION).unit
            == MetricUnit.PIXELS_PER_SECOND_SQUARED
        )


def test_diagonal_displacement_uses_the_euclidean_distance() -> None:
    observations = [
        point(frame_index=0, timestamp_seconds=0.0, x1=0, y1=0, x2=0, y2=0),
        point(frame_index=1, timestamp_seconds=1.0, x1=3, y1=4, x2=3, y2=4),
    ]
    metrics = MetricCalculator(max_gap_seconds=MAX_GAP).calculate(1, observations)

    assert metrics.value_for(MetricName.DISPLACEMENT).value == pytest.approx(math.hypot(3, 4))
