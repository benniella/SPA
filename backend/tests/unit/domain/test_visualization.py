from __future__ import annotations

import pytest

from app.domain.metrics.types import TrackObservationPoint
from app.domain.visualization.types import (
    build_activity_timeline,
    build_density_grid,
    build_track_paths,
    coordinate_bounds,
)


def point(
    *,
    track_id: int = 1,
    frame_index: int = 0,
    timestamp_seconds: float = 0.0,
    x1: float = 10.0,
    y1: float = 10.0,
    width: float = 10.0,
    height: float = 10.0,
    confidence: float = 0.9,
) -> TrackObservationPoint:
    return TrackObservationPoint(
        track_id=track_id,
        frame_index=frame_index,
        timestamp_seconds=timestamp_seconds,
        x1=x1,
        y1=y1,
        x2=x1 + width,
        y2=y1 + height,
        confidence=confidence,
    )


class TestTrackPaths:
    def test_orders_points_by_frame_regardless_of_input_order(self) -> None:
        observations = [
            point(frame_index=2, timestamp_seconds=1.0, x1=30.0),
            point(frame_index=0, timestamp_seconds=0.0, x1=10.0),
            point(frame_index=1, timestamp_seconds=0.5, x1=20.0),
        ]

        paths = build_track_paths(observations, max_points_per_track=10)

        assert len(paths) == 1
        assert [p.x for p in paths[0].points] == [15.0, 25.0, 35.0]
        assert [p.frame_index for p in paths[0].points] == [0, 1, 2]

    def test_separates_tracks_and_orders_them_by_identifier(self) -> None:
        observations = [
            point(track_id=2, frame_index=0, x1=40.0),
            point(track_id=1, frame_index=0, x1=10.0),
        ]

        paths = build_track_paths(observations, max_points_per_track=10)

        assert [path.track_id for path in paths] == [1, 2]

    def test_downsampling_keeps_the_first_and_last_point(self) -> None:
        observations = [
            point(frame_index=i, timestamp_seconds=float(i), x1=float(i * 10)) for i in range(100)
        ]

        paths = build_track_paths(observations, max_points_per_track=5)

        kept = paths[0].points
        assert len(kept) == 5
        assert kept[0].frame_index == 0
        assert kept[-1].frame_index == 99
        assert paths[0].observation_count == 100
        assert paths[0].downsampled is True

    def test_the_same_observations_produce_the_same_path(self) -> None:
        observations = [point(frame_index=i, timestamp_seconds=float(i)) for i in range(50)]

        first = build_track_paths(observations, max_points_per_track=7)
        second = build_track_paths(list(reversed(observations)), max_points_per_track=7)

        assert [(p.frame_index, p.x, p.y) for p in first[0].points] == [
            (p.frame_index, p.x, p.y) for p in second[0].points
        ]

    def test_an_empty_observation_set_yields_no_paths(self) -> None:
        assert build_track_paths([], max_points_per_track=10) == ()

    def test_a_limit_below_two_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_track_paths([], max_points_per_track=1)


class TestDensityGrid:
    def test_counts_observations_into_the_expected_cells(self) -> None:
        observations = [
            point(x1=10.0, y1=10.0),
            point(x1=12.0, y1=12.0),
            point(x1=80.0, y1=80.0),
        ]

        grid = build_density_grid(observations, columns=2, rows=2, bounds=(0.0, 0.0, 100.0, 100.0))

        assert grid.counts == (2, 0, 0, 1)
        assert grid.max_count == 2
        assert grid.observation_count == 3
        assert grid.track_count == 1

    def test_a_point_on_the_far_edge_lands_in_the_final_cell(self) -> None:
        observations = [point(x1=190.0, y1=100.0, width=10.0, height=10.0)]

        grid = build_density_grid(observations, columns=4, rows=4, bounds=(0.0, 0.0, 200.0, 120.0))

        assert grid.counts[-1] == 1

    def test_binning_is_deterministic_and_order_independent(self) -> None:
        observations = [point(x1=float(i * 7), y1=float(i * 5), frame_index=i) for i in range(40)]

        first = build_density_grid(observations, columns=8, rows=6, bounds=(0.0, 0.0, 400.0, 300.0))
        second = build_density_grid(
            list(reversed(observations)), columns=8, rows=6, bounds=(0.0, 0.0, 400.0, 300.0)
        )

        assert first.counts == second.counts
        assert sum(first.counts) == len(observations)

    def test_intensity_is_normalized_against_the_largest_cell(self) -> None:
        observations = [
            point(x1=10.0, y1=10.0),
            point(x1=12.0, y1=12.0),
            point(x1=80.0, y1=80.0),
        ]

        grid = build_density_grid(observations, columns=2, rows=2, bounds=(0.0, 0.0, 100.0, 100.0))

        assert grid.intensity(0) == pytest.approx(1.0)
        assert grid.intensity(3) == pytest.approx(0.5)

    def test_filtering_by_track_changes_the_counts(self) -> None:
        observations = [
            point(track_id=1, x1=10.0, y1=10.0),
            point(track_id=2, x1=80.0, y1=80.0),
            point(track_id=2, x1=82.0, y1=82.0),
        ]

        grid = build_density_grid(
            observations,
            columns=2,
            rows=2,
            track_ids=frozenset({2}),
            bounds=(0.0, 0.0, 100.0, 100.0),
        )

        assert grid.counts == (0, 0, 0, 2)
        assert grid.track_count == 1

    def test_no_observations_produce_an_empty_grid(self) -> None:
        grid = build_density_grid([], columns=3, rows=3, bounds=(0.0, 0.0, 90.0, 90.0))

        assert grid.counts == (0,) * 9
        assert grid.max_count == 0
        assert grid.intensity(0) == 0.0

    def test_the_observed_bounds_are_used_when_no_extent_is_supplied(self) -> None:
        observations = [point(x1=100.0, y1=200.0), point(x1=300.0, y1=400.0)]

        grid = build_density_grid(observations, columns=2, rows=2)

        assert grid.bounds == (105.0, 205.0, 305.0, 405.0)


class TestActivityTimeline:
    def test_buckets_observations_over_the_time_span(self) -> None:
        observations = [
            point(track_id=1, timestamp_seconds=0.0),
            point(track_id=2, timestamp_seconds=1.0),
            point(track_id=1, timestamp_seconds=6.0),
        ]

        timeline = build_activity_timeline(observations, bucket_seconds=5.0)

        assert timeline.start_seconds == 0.0
        assert timeline.end_seconds == 6.0
        assert len(timeline.buckets) == 2
        assert timeline.buckets[0].observation_count == 2
        assert timeline.buckets[0].track_ids == (1, 2)
        assert timeline.buckets[1].observation_count == 1
        assert timeline.max_count == 2

    def test_an_empty_set_produces_no_buckets(self) -> None:
        timeline = build_activity_timeline([], bucket_seconds=5.0)

        assert timeline.buckets == ()
        assert timeline.max_count == 0

    def test_a_non_positive_bucket_size_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            build_activity_timeline([point()], bucket_seconds=0.0)


class TestCoordinateBounds:
    def test_an_empty_set_yields_a_one_pixel_span(self) -> None:
        assert coordinate_bounds([]) == (0.0, 0.0, 1.0, 1.0)

    def test_a_single_point_does_not_collapse_the_span(self) -> None:
        left, top, right, bottom = coordinate_bounds([point(x1=50.0, y1=60.0)])

        assert (left, top) == (55.0, 65.0)
        assert right > left
        assert bottom > top
