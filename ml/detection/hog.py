from __future__ import annotations

import cv2
import numpy as np
import numpy.typing as npt

from ml.detection.detector import DetectorConfig, Frame
from ml.detection.types import PERSON_CLASS_ID, PERSON_LABEL, BoundingBox, Detection


class CudaUnavailableError(RuntimeError):
    """A CUDA device was requested but OpenCV has none available."""


class DetectorUnavailableError(RuntimeError):
    """The OpenCV build lacks the primitives the detector needs."""


class HogPersonDetector:
    """Person detection using OpenCV's built-in HOG + linear SVM descriptor.

    Chosen as the first concrete detector because it ships with OpenCV: it needs
    no weights file, no download and no GPU, so CPU development and the test
    suite work out of the box. It is a classical detector and less accurate than
    a modern network on wide-angle sports footage, which is exactly why the
    detector is an interface — a YOLO-class implementation can replace it
    without the pipeline changing.
    """

    def __init__(self, config: DetectorConfig) -> None:
        if config.device == "cuda" and (
            not hasattr(cv2, "cuda") or cv2.cuda.getCudaEnabledDeviceCount() < 1
        ):
            raise CudaUnavailableError(
                "CV_DEVICE is 'cuda' but no CUDA device is available to OpenCV."
            )
        # The built-in HOG descriptor has no CUDA path; the configured device is
        # recorded but inference stays on the CPU rather than failing.
        self._config = config
        self._hog = cv2.HOGDescriptor()
        self._hog.setSVMDetector(_default_people_detector())

    @property
    def name(self) -> str:
        return "hog_person"

    def detect(self, frame: Frame) -> list[Detection]:
        if frame.size == 0:
            return []
        gray = self._to_gray(frame)
        rects, weights = self._hog.detectMultiScale(
            gray,
            winStride=(8, 8),
            padding=(8, 8),
            scale=1.05,
        )
        detections: list[Detection] = []
        for (x, y, width, height), weight in zip(rects, weights, strict=False):
            confidence = float(weight)
            if confidence < self._config.confidence_threshold:
                continue
            if height < self._config.min_box_height:
                continue
            box = _clamp_box(
                BoundingBox(
                    x1=float(x),
                    y1=float(y),
                    x2=float(x + width),
                    y2=float(y + height),
                ),
                width=gray.shape[1],
                height=gray.shape[0],
            )
            if box.width <= 0 or box.height <= 0:
                continue
            detections.append(
                Detection(
                    class_id=PERSON_CLASS_ID,
                    label=PERSON_LABEL,
                    confidence=min(max(confidence, 0.0), 1.0),
                    box=box,
                )
            )
        return detections

    @staticmethod
    def _to_gray(frame: Frame) -> npt.NDArray[np.integer | np.floating]:
        if frame.ndim == 2:
            return frame
        if frame.shape[2] == 4:
            converted = cv2.cvtColor(frame, cv2.COLOR_BGRA2GRAY)
        else:
            converted = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        return np.ascontiguousarray(converted)


def _default_people_detector() -> npt.NDArray[np.float32]:
    # OpenCV's type stubs omit this function even though it is present at
    # runtime, so the access is narrowed here rather than suppressed at the call.
    if not hasattr(cv2, "HOGDescriptor_getDefaultPeopleDetector"):
        raise DetectorUnavailableError("This OpenCV build has no default people detector.")
    getter = cv2.HOGDescriptor_getDefaultPeopleDetector  # type: ignore[attr-defined]
    result: npt.NDArray[np.float32] = getter()
    return result


def _clamp_box(box: BoundingBox, *, width: int, height: int) -> BoundingBox:
    return BoundingBox(
        x1=max(0.0, min(box.x1, float(width))),
        y1=max(0.0, min(box.y1, float(height))),
        x2=max(0.0, min(box.x2, float(width))),
        y2=max(0.0, min(box.y2, float(height))),
    )
