from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from ml.detection.types import BoundingBox, Detection, Track
from ml.tracking.tracker import TrackerConfig


@dataclass(slots=True)
class _ActiveTrack:
    track_id: int
    class_id: int
    label: str
    box: BoundingBox
    confidence: float
    missed_frames: int = 0

    @property
    def center(self) -> tuple[float, float]:
        return ((self.box.x1 + self.box.x2) / 2.0, (self.box.y1 + self.box.y2) / 2.0)


class CentroidTracker:
    """Associates detections to tracks by nearest centre distance.

    Deliberately simple and deterministic: nearest-neighbour greedy matching over
    centre distance, with a per-track miss budget so a briefly occluded object
    keeps its identity. It has no motion model and no appearance model, so it
    tolerates temporary missed detections but not long occlusions or crossings.
    A Kalman- or IoU-based tracker replaces it behind the same interface when
    tracking quality becomes the priority.
    """

    def __init__(self, config: TrackerConfig | None = None) -> None:
        self._config = config or TrackerConfig()
        self._tracks: dict[int, _ActiveTrack] = {}
        self._next_id = 1

    @property
    def name(self) -> str:
        return "centroid"

    def update(
        self,
        detections: list[Detection],
        *,
        frame_index: int,
        timestamp_seconds: float,
    ) -> list[Track]:
        assigned = self._associate(detections)
        tracks: list[Track] = []

        for detection_index, track_id in assigned.items():
            detection = detections[detection_index]
            state = self._tracks[track_id]
            state.box = detection.box
            state.confidence = detection.confidence
            state.missed_frames = 0
            tracks.append(
                Track(
                    track_id=track_id,
                    class_id=detection.class_id,
                    label=detection.label,
                    confidence=detection.confidence,
                    box=detection.box,
                    frame_index=frame_index,
                    timestamp_seconds=timestamp_seconds,
                )
            )

        self._age_unmatched(assigned.values())
        return tracks

    def _associate(self, detections: list[Detection]) -> dict[int, int]:
        """Greedy nearest-centre matching; returns detection index -> track id."""
        candidates: list[tuple[float, int, int]] = []
        for detection_index, detection in enumerate(detections):
            center = _center(detection.box)
            for track_id, state in self._tracks.items():
                if state.class_id != detection.class_id:
                    continue
                distance = _distance(center, state.center)
                if distance <= self._config.max_distance_px:
                    candidates.append((distance, detection_index, track_id))

        candidates.sort(key=lambda candidate: (candidate[0], candidate[1], candidate[2]))

        assigned: dict[int, int] = {}
        used_tracks: set[int] = set()
        for _, detection_index, track_id in candidates:
            if detection_index in assigned or track_id in used_tracks:
                continue
            assigned[detection_index] = track_id
            used_tracks.add(track_id)

        for detection_index, detection in enumerate(detections):
            if detection_index in assigned:
                continue
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = _ActiveTrack(
                track_id=track_id,
                class_id=detection.class_id,
                label=detection.label,
                box=detection.box,
                confidence=detection.confidence,
            )
            assigned[detection_index] = track_id
            used_tracks.add(track_id)

        return assigned

    def _age_unmatched(self, matched_track_ids: Collection[int]) -> None:
        matched = set(matched_track_ids)
        expired: list[int] = []
        for track_id, state in self._tracks.items():
            if track_id in matched:
                continue
            state.missed_frames += 1
            if state.missed_frames > self._config.max_missed_frames:
                expired.append(track_id)
        for track_id in expired:
            del self._tracks[track_id]


def _center(box: BoundingBox) -> tuple[float, float]:
    return ((box.x1 + box.x2) / 2.0, (box.y1 + box.y2) / 2.0)


def _distance(a: tuple[float, float], b: tuple[float, float]) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
