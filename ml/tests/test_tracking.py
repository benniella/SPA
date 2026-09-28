from __future__ import annotations

from ml.tests.conftest import person_box
from ml.tracking.centroid import CentroidTracker
from ml.tracking.registry import UnknownTrackerError, available_trackers, build_tracker
from ml.tracking.tracker import TrackerConfig


def update(tracker: CentroidTracker, detections: list, frame_index: int = 0) -> list:
    return tracker.update(detections, frame_index=frame_index, timestamp_seconds=frame_index / 10.0)


class TestTrackerContract:
    def test_the_default_tracker_is_registered(self) -> None:
        assert "centroid" in available_trackers()

    def test_an_unknown_tracker_name_is_rejected(self) -> None:
        try:
            build_tracker("not-a-tracker")
        except UnknownTrackerError:
            return
        raise AssertionError("an unknown tracker name must be rejected")

    def test_a_track_carries_identity_position_and_time(self) -> None:
        tracker = CentroidTracker()
        tracks = update(tracker, [person_box(100, 100)], frame_index=3)

        assert len(tracks) == 1
        track = tracks[0]
        assert track.track_id >= 0
        assert track.frame_index == 3
        assert track.timestamp_seconds == 0.3
        assert track.box.x1 == 100


class TestStableIdentity:
    def test_a_moving_object_keeps_its_id_across_frames(self) -> None:
        tracker = CentroidTracker()
        first = update(tracker, [person_box(100, 100)], frame_index=0)
        second = update(tracker, [person_box(110, 100)], frame_index=1)
        third = update(tracker, [person_box(120, 100)], frame_index=2)

        assert first[0].track_id == second[0].track_id == third[0].track_id

    def test_a_distant_object_gets_a_new_id(self) -> None:
        tracker = CentroidTracker(TrackerConfig(max_distance_px=30))
        first = update(tracker, [person_box(0, 0)], frame_index=0)
        second = update(tracker, [person_box(500, 500)], frame_index=1)

        assert first[0].track_id != second[0].track_id


class TestMultipleObjects:
    def test_two_people_tracked_independently(self) -> None:
        tracker = CentroidTracker()
        tracks = update(tracker, [person_box(0, 0), person_box(200, 0)], frame_index=0)

        assert len(tracks) == 2
        assert tracks[0].track_id != tracks[1].track_id

    def test_ids_survive_a_frame_with_reordered_detections(self) -> None:
        tracker = CentroidTracker()
        first = update(tracker, [person_box(0, 0), person_box(200, 0)], frame_index=0)
        ids_by_x = {track.box.x1: track.track_id for track in first}

        second = update(tracker, [person_box(205, 0), person_box(5, 0)], frame_index=1)
        for track in second:
            nearest = 0 if track.box.x1 < 100 else 200
            assert track.track_id == ids_by_x[nearest]


class TestMissedDetections:
    def test_a_briefly_missed_object_keeps_its_id(self) -> None:
        tracker = CentroidTracker(TrackerConfig(max_distance_px=200, max_missed_frames=5))
        first = update(tracker, [person_box(100, 100)], frame_index=0)
        update(tracker, [], frame_index=1)
        third = update(tracker, [person_box(120, 100)], frame_index=2)

        assert third[0].track_id == first[0].track_id

    def test_a_long_absence_retires_the_id(self) -> None:
        tracker = CentroidTracker(TrackerConfig(max_distance_px=200, max_missed_frames=1))
        first = update(tracker, [person_box(100, 100)], frame_index=0)
        update(tracker, [], frame_index=1)
        update(tracker, [], frame_index=2)
        fourth = update(tracker, [person_box(100, 100)], frame_index=3)

        assert fourth[0].track_id != first[0].track_id


class TestEmptyInput:
    def test_no_detections_yields_no_tracks(self) -> None:
        tracker = CentroidTracker()
        assert update(tracker, []) == []

    def test_an_empty_frame_does_not_create_ids(self) -> None:
        tracker = CentroidTracker()
        update(tracker, [])
        tracks = update(tracker, [person_box(0, 0)], frame_index=1)

        assert tracks[0].track_id == 1
