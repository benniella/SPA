"""Deterministic movement metrics over a single track's observations.

Every function here is pure: the same observations always produce the same
numbers. Observations are ordered by frame index and then timestamp, and an
interval that would imply movement across a tracking gap, a duplicate frame or a
non-positive time step is skipped rather than interpreted as motion.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from itertools import pairwise

from app.domain.metrics.types import (
    MetricName,
    MetricUnit,
    MetricValue,
    TrackObservationPoint,
)

MIN_MOVEMENT_OBSERVATIONS = 2
MIN_ACCELERATION_OBSERVATIONS = 3


def canonical_order(
    observations: Iterable[TrackObservationPoint],
) -> list[TrackObservationPoint]:
    """Order observations deterministically by frame, then timestamp.

    Frame index leads because two observations in one frame are a duplicate, not
    a movement step, and ordering by time first would let an unstable timestamp
    reorder the same frames differently between runs.
    """
    return sorted(observations, key=lambda point: (point.frame_index, point.timestamp_seconds))


def displacement(
    observations: list[TrackObservationPoint], *, max_gap_seconds: float
) -> MetricValue:
    """Total distance travelled between consecutive observations, in pixels."""
    total = 0.0
    sample_count = 0
    for previous, current in _consecutive_steps(observations, max_gap_seconds=max_gap_seconds):
        total += _distance(previous, current)
        sample_count += 1

    if sample_count == 0:
        return MetricValue.unavailable(
            MetricName.DISPLACEMENT, MetricUnit.PIXELS, sample_count=len(observations)
        )
    return MetricValue.available(
        MetricName.DISPLACEMENT, MetricUnit.PIXELS, total, sample_count=sample_count
    )


def average_speed(
    observations: list[TrackObservationPoint], *, max_gap_seconds: float
) -> MetricValue:
    """Mean source-space speed over every usable interval, in pixels per second."""
    speeds = _interval_speeds(observations, max_gap_seconds=max_gap_seconds)
    if not speeds:
        return MetricValue.unavailable(
            MetricName.AVERAGE_SPEED,
            MetricUnit.PIXELS_PER_SECOND,
            sample_count=len(observations),
        )
    return MetricValue.available(
        MetricName.AVERAGE_SPEED,
        MetricUnit.PIXELS_PER_SECOND,
        sum(speeds) / len(speeds),
        sample_count=len(speeds),
    )


def peak_speed(observations: list[TrackObservationPoint], *, max_gap_seconds: float) -> MetricValue:
    """The fastest usable interval, in pixels per second.

    This is the peak of a sampled interval, not a player's physical top speed:
    the sample rate bounds what can be observed and no calibration exists.
    """
    speeds = _interval_speeds(observations, max_gap_seconds=max_gap_seconds)
    if not speeds:
        return MetricValue.unavailable(
            MetricName.PEAK_SPEED,
            MetricUnit.PIXELS_PER_SECOND,
            sample_count=len(observations),
        )
    return MetricValue.available(
        MetricName.PEAK_SPEED,
        MetricUnit.PIXELS_PER_SECOND,
        max(speeds),
        sample_count=len(speeds),
    )


def average_acceleration(
    observations: list[TrackObservationPoint], *, max_gap_seconds: float
) -> MetricValue:
    """Mean change in velocity over time, in pixels per second squared."""
    accelerations = _accelerations(observations, max_gap_seconds=max_gap_seconds)
    if not accelerations:
        return MetricValue.unavailable(
            MetricName.AVERAGE_ACCELERATION,
            MetricUnit.PIXELS_PER_SECOND_SQUARED,
            sample_count=len(observations),
        )
    return MetricValue.available(
        MetricName.AVERAGE_ACCELERATION,
        MetricUnit.PIXELS_PER_SECOND_SQUARED,
        sum(accelerations) / len(accelerations),
        sample_count=len(accelerations),
    )


def peak_acceleration(
    observations: list[TrackObservationPoint], *, max_gap_seconds: float
) -> MetricValue:
    """The largest change in velocity over time, in pixels per second squared."""
    accelerations = _accelerations(observations, max_gap_seconds=max_gap_seconds)
    if not accelerations:
        return MetricValue.unavailable(
            MetricName.PEAK_ACCELERATION,
            MetricUnit.PIXELS_PER_SECOND_SQUARED,
            sample_count=len(observations),
        )
    return MetricValue.available(
        MetricName.PEAK_ACCELERATION,
        MetricUnit.PIXELS_PER_SECOND_SQUARED,
        max(accelerations),
        sample_count=len(accelerations),
    )


def _consecutive_steps(
    observations: list[TrackObservationPoint],
    *,
    max_gap_seconds: float,
) -> list[tuple[TrackObservationPoint, TrackObservationPoint]]:
    """Adjacent observation pairs that represent real, continuous movement.

    A pair is rejected when it repeats a frame, when time does not advance, or
    when the gap exceeds ``max_gap_seconds`` — a track that disappeared for a
    minute must not read as a player who sprinted across the pitch.
    """
    steps: list[tuple[TrackObservationPoint, TrackObservationPoint]] = []
    for previous, current in pairwise(observations):
        if current.frame_index <= previous.frame_index:
            continue
        elapsed = current.timestamp_seconds - previous.timestamp_seconds
        if elapsed <= 0.0 or elapsed > max_gap_seconds:
            continue
        steps.append((previous, current))
    return steps


def _interval_speeds(
    observations: list[TrackObservationPoint],
    *,
    max_gap_seconds: float,
) -> list[float]:
    speeds: list[float] = []
    for previous, current in _consecutive_steps(observations, max_gap_seconds=max_gap_seconds):
        elapsed = current.timestamp_seconds - previous.timestamp_seconds
        speeds.append(_distance(previous, current) / elapsed)
    return speeds


def _accelerations(
    observations: list[TrackObservationPoint],
    *,
    max_gap_seconds: float,
) -> list[float]:
    """Velocity changes between consecutive usable intervals.

    Two usable intervals are required, so a track with only two observations has
    no acceleration rather than a value invented from a zero initial velocity.
    """
    intervals: list[tuple[float, float]] = []
    for previous, current in _consecutive_steps(observations, max_gap_seconds=max_gap_seconds):
        elapsed = current.timestamp_seconds - previous.timestamp_seconds
        velocity = _distance(previous, current) / elapsed
        midpoint = previous.timestamp_seconds + elapsed / 2.0
        intervals.append((midpoint, velocity))

    accelerations: list[float] = []
    for (earlier_time, earlier_velocity), (later_time, later_velocity) in pairwise(intervals):
        delta_time = later_time - earlier_time
        if delta_time <= 0.0:
            continue
        accelerations.append((later_velocity - earlier_velocity) / delta_time)
    return accelerations


def _distance(first: TrackObservationPoint, second: TrackObservationPoint) -> float:
    return math.hypot(second.center_x - first.center_x, second.center_y - first.center_y)
