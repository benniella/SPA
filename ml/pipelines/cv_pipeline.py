from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from ml.detection.detector import Detector, DetectorConfig
from ml.detection.registry import build_detector
from ml.detection.types import Track
from ml.tracking.registry import build_tracker
from ml.tracking.tracker import Tracker, TrackerConfig
from ml.video.decoder import VideoDecoder
from ml.video.opencv_decoder import OpenCvVideoDecoder
from ml.video.sampling import FixedIntervalSampler
from ml.video.types import VideoMetadata


@dataclass(frozen=True, slots=True)
class CvPipelineConfig:
    """Everything the CV pipeline needs, resolved from backend configuration.

    The detector name is a registry key, never a filesystem path or a
    client-supplied value, so nothing here can cause the worker to execute
    arbitrary code.
    """

    detector_name: str = "hog_person"
    tracker_name: str = "centroid"
    confidence_threshold: float = 0.5
    device: str = "cpu"
    model_path: str = ""
    frame_interval: int = 5
    min_box_height: int = 24
    max_association_distance_px: float = 80.0
    max_missed_frames: int = 8


@dataclass(slots=True)
class CvRunResult:
    """What one pipeline execution produced, in aggregate.

    Only counters travel here: the tracks themselves are consumed by the
    callback and never accumulated, so a match-long video does not grow memory.
    """

    frames_sampled: int = 0
    detections: int = 0
    tracks: int = 0
    metadata: VideoMetadata | None = None
    track_ids: set[int] = field(default_factory=set)


TrackSink = Callable[[list[Track]], None]
ProgressCallback = Callable[[int, int], None]


class CvPipeline:
    """Video → frames → detections → tracks, one sampled frame at a time.

    The detector and tracker are built once per run and injected, so their
    lifecycle is explicit and neither is reloaded per frame. The pipeline owns no
    persistence: tracks are handed to a sink, which keeps the CV layer
    independent of the database.
    """

    def __init__(
        self,
        config: CvPipelineConfig,
        *,
        decoder_factory: Callable[[str], VideoDecoder] = lambda path: OpenCvVideoDecoder(path),
        detector: Detector | None = None,
        tracker: Tracker | None = None,
    ) -> None:
        self._config = config
        self._decoder_factory = decoder_factory
        self._detector = detector or build_detector(
            config.detector_name,
            DetectorConfig(
                confidence_threshold=config.confidence_threshold,
                device=config.device,
                model_path=config.model_path,
                min_box_height=config.min_box_height,
            ),
        )
        self._tracker = tracker or build_tracker(
            config.tracker_name,
            TrackerConfig(
                max_distance_px=config.max_association_distance_px,
                max_missed_frames=config.max_missed_frames,
            ),
        )

    @property
    def detector_name(self) -> str:
        return self._detector.name

    @property
    def tracker_name(self) -> str:
        return self._tracker.name

    def run(
        self,
        path: str,
        *,
        on_tracks: TrackSink,
        on_progress: ProgressCallback | None = None,
    ) -> CvRunResult:
        sampler = FixedIntervalSampler(self._config.frame_interval)
        result = CvRunResult()

        with self._decoder_factory(path) as decoder:
            metadata = decoder.metadata
            result.metadata = metadata
            indices = sampler.indices(frame_count=metadata.frame_count or 0)
            total = len(range(0, metadata.frame_count or 0, self._config.frame_interval))
            for decoded in decoder.frames(iter(indices)):
                detections = self._detector.detect(decoded.data)
                frame_tracks = self._tracker.update(
                    detections,
                    frame_index=decoded.index,
                    timestamp_seconds=decoded.timestamp_seconds,
                )
                result.frames_sampled += 1
                result.detections += len(detections)
                result.tracks += len(frame_tracks)
                result.track_ids.update(track.track_id for track in frame_tracks)
                if frame_tracks:
                    on_tracks(frame_tracks)
                if on_progress is not None and total:
                    on_progress(result.frames_sampled, total)

        return result
