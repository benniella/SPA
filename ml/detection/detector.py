from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np
import numpy.typing as npt

from ml.detection.types import Detection

#: A decoded image array. The dtype is left open because OpenCV's stubs do not
#: narrow the dtype of a captured frame.
Frame = npt.NDArray[np.integer | np.floating]

@dataclass(frozen=True, slots=True)
class DetectorConfig:
    """Parameters a detector needs, resolved from backend configuration.

    'model_path' is empty for detectors that need no weights file; it is a
    server-side value, never supplied by a client.
    """

    confidence_threshold: float = 0.5
    device: str = "cpu"
    model_path: str = ""
    min_box_height: int = 24


@runtime_checkable
class Detector(Protocol):
    """Finds objects in a single frame.

    Implementations own their model and are constructed once per pipeline run;
    they never track across frames, which keeps detection and tracking
    independently replaceable.
    """

    @property
    def name(self) -> str: ...

    def detect(self, frame: Frame) -> list[Detection]: ...
