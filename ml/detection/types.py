from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BoundingBox:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("A bounding box requires x2 >= x1 and y2 >= y1.")

    @property
    def width(self) -> float:
        return self.x2 - self.x1

    @property
    def height(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.width * self.height

    def as_tuple(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


@dataclass(frozen=True, slots=True)
class Detection:
    """One object found in one frame, in source-image pixel coordinates."""

    class_id: int
    label: str
    confidence: float
    box: BoundingBox

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1.")


@dataclass(frozen=True, slots=True)
class Track:
    """One object's identity in one frame, carried forward by a tracker."""

    track_id: int
    class_id: int
    label: str
    confidence: float
    box: BoundingBox
    frame_index: int
    timestamp_seconds: float

    def __post_init__(self) -> None:
        if self.track_id < 0:
            raise ValueError("track_id cannot be negative.")
        if self.frame_index < 0:
            raise ValueError("frame_index cannot be negative.")
        if self.timestamp_seconds < 0:
            raise ValueError("timestamp_seconds cannot be negative.")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0 and 1.")


PERSON_CLASS_ID = 0
PERSON_LABEL = "person"
