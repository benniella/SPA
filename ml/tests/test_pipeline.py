from __future__ import annotations

from pathlib import Path

import pytest

from ml.detection.detector import Detector
from ml.detection.types import Detection, Track
from ml.pipelines.cv_pipeline import CvPipeline, CvPipelineConfig
from ml.tests.conftest import person_box, write_video
from ml.tracking.tracker import Tracker
from ml.video.types import VideoDecodeError


class ScriptedDetector:
    """Returns one detection per sampled frame, on a diagonal path."""

    def __init__(self) -> None:
        self.frames_seen = 0

    @property
    def name(self) -> str:
        return "scripted"

    def detect(self, frame: object) -> list[Detection]:
        offset = self.frames_seen * 5
        self.frames_seen += 1
        return [person_box(10 + offset, 10 + offset)]


class EmptyDetector:
    @property
    def name(self) -> str:
        return "empty"

    def detect(self, frame: object) -> list[Detection]:
        return []


def run_pipeline(
    path: Path,
    *,
    detector: Detector,
    frame_interval: int = 5,
) -> tuple[object, list[Track]]:
    pipeline = CvPipeline(
        CvPipelineConfig(frame_interval=frame_interval),
        detector=detector,
    )
    collected: list[Track] = []
    result = pipeline.run(str(path), on_tracks=collected.extend)
    return result, collected


class TestDetectorTrackerIntegration:
    def test_detections_become_tracks(self, synthetic_video: Path) -> None:
        result, tracks = run_pipeline(synthetic_video, detector=ScriptedDetector())

        assert result.frames_sampled == 4
        assert result.detections == 4
        assert len(tracks) == 4

    def test_tracking_assigns_stable_ids_to_a_moving_object(
        self, synthetic_video: Path
    ) -> None:
        result, _ = run_pipeline(synthetic_video, detector=ScriptedDetector())

        assert len(result.track_ids) == 1

    def test_the_tracker_receives_the_detectors_output_unchanged(
        self, synthetic_video: Path
    ) -> None:
        _, tracks = run_pipeline(synthetic_video, detector=ScriptedDetector())

        assert [track.frame_index for track in tracks] == [0, 5, 10, 15]


class TestEmptyDetection:
    def test_a_video_with_no_detections_completes_cleanly(
        self, synthetic_video: Path
    ) -> None:
        result, tracks = run_pipeline(synthetic_video, detector=EmptyDetector())

        assert tracks == []
        assert result.detections == 0
        assert result.tracks == 0
        assert result.frames_sampled == 4


class TestProgress:
    def test_progress_is_reported_per_sampled_frame(self, synthetic_video: Path) -> None:
        seen: list[tuple[int, int]] = []
        pipeline = CvPipeline(
            CvPipelineConfig(frame_interval=5),
            detector=ScriptedDetector(),
        )

        pipeline.run(
            str(synthetic_video),
            on_tracks=lambda tracks: None,
            on_progress=lambda processed, total: seen.append((processed, total)),
        )

        assert seen == [(1, 4), (2, 4), (3, 4), (4, 4)]

    def test_frame_interval_changes_how_many_frames_are_sampled(
        self, synthetic_video: Path
    ) -> None:
        result, _ = run_pipeline(synthetic_video, detector=ScriptedDetector(), frame_interval=10)

        assert result.frames_sampled == 2


class TestResourceBoundaries:
    def test_tracks_are_handed_over_rather_than_accumulated(self, synthetic_video: Path) -> None:
        write_video(synthetic_video, frames=100)
        batches: list[int] = []
        pipeline = CvPipeline(
            CvPipelineConfig(frame_interval=1),
            detector=ScriptedDetector(),
        )

        result = pipeline.run(
            str(synthetic_video),
            on_tracks=lambda tracks: batches.append(len(tracks)),
        )

        # One callback per sampled frame: the sink, not the pipeline, decides
        # how much is retained.
        assert len(batches) == result.frames_sampled == 100


class TestFailure:
    def test_an_invalid_video_raises_a_decode_error(self, tmp_path: Path) -> None:
        pipeline = CvPipeline(CvPipelineConfig(), detector=ScriptedDetector())

        with pytest.raises(VideoDecodeError):
            pipeline.run(str(tmp_path / "absent.mp4"), on_tracks=lambda tracks: None)


def test_a_tracker_can_be_injected_independently(synthetic_video: Path) -> None:
    class FixedTracker:
        @property
        def name(self) -> str:
            return "fixed"

        def update(self, detections: list, *, frame_index: int, timestamp_seconds: float) -> list:
            return [
                Track(
                    track_id=42,
                    class_id=detection.class_id,
                    label=detection.label,
                    confidence=detection.confidence,
                    box=detection.box,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                )
                for detection in detections
            ]

    tracker: Tracker = FixedTracker()
    pipeline = CvPipeline(
        CvPipelineConfig(frame_interval=5),
        detector=ScriptedDetector(),
        tracker=tracker,
    )
    collected: list[Track] = []
    pipeline.run(str(synthetic_video), on_tracks=collected.extend)

    assert {track.track_id for track in collected} == {42}
