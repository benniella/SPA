from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ml.detection.types import Detection, Track


@dataclass(frozen=True, slots=True)
class TrackerConfig:
    """Association parameters for a multi-object tracker.

    'max_distance_px' is expressed in the frame's own pixels because no pitch
    calibration exists yet; a future tracker that works in pitch metres takes a
    different config, which is why this is a value object rather than constants
    inside the tracker.
    """

    max_distance_px: float = 80.0
    max_missed_frames: int = 8


@runtime_checkable
class Tracker(Protocol):
    """Associates per-frame detections into stable track identities.

    A tracker consumes detector output without knowing which detector produced
    it, so the two are independently replaceable.
    """

    @property
    def name(self) -> str: ...

    def update(
        self,
        detections: list[Detection],
        *,
        frame_index: int,
        timestamp_seconds: float,
    ) -> list[Track]: ...
