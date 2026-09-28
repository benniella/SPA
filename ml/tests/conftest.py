from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from ml.detection.types import BoundingBox, Detection, Track


def write_video(
    path: Path,
    *,
    frames: int = 20,
    fps: float = 10.0,
    width: int = 320,
    height: int = 240,
) -> Path:
    """Write a tiny synthetic clip: a light block moving across a dark frame."""
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    assert writer.isOpened(), "no usable test codec in this OpenCV build"
    for index in range(frames):
        frame = np.full((height, width, 3), 30, dtype=np.uint8)
        left = 10 + index * 5
        cv2.rectangle(frame, (left, 60), (left + 40, 200), (200, 200, 200), -1)
        writer.write(frame)
    writer.release()
    return path


@pytest.fixture
def synthetic_video(tmp_path: Path) -> Path:
    return write_video(tmp_path / "clip.mp4")


def person_box(
    x: float, y: float, *, size: float = 40.0, confidence: float = 0.9
) -> Detection:
    return Detection(
        class_id=0,
        label="person",
        confidence=confidence,
        box=BoundingBox(x1=x, y1=y, x2=x + size, y2=y + size),
    )


def track_at(track_id: int, x: float, y: float, *, frame_index: int = 0) -> Track:
    return Track(
        track_id=track_id,
        class_id=0,
        label="person",
        confidence=0.9,
        box=BoundingBox(x1=x, y1=y, x2=x + 40, y2=y + 40),
        frame_index=frame_index,
        timestamp_seconds=frame_index / 10.0,
    )
