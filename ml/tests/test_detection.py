from __future__ import annotations

import numpy as np
import pytest

from ml.detection.detector import DetectorConfig
from ml.detection.hog import CudaUnavailableError, HogPersonDetector
from ml.detection.registry import UnknownDetectorError, available_detectors, build_detector
from ml.detection.types import PERSON_CLASS_ID, BoundingBox, Detection


class TestDetectionContract:
    def test_a_detection_carries_a_label_confidence_and_box(self) -> None:
        detection = Detection(
            class_id=PERSON_CLASS_ID,
            label="person",
            confidence=0.91,
            box=BoundingBox(x1=10, y1=20, x2=60, y2=120),
        )

        assert detection.label == "person"
        assert detection.confidence == 0.91
        assert detection.box.width == 50
        assert detection.box.height == 100

    def test_a_confidence_outside_zero_to_one_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            Detection(class_id=0, label="person", confidence=1.5, box=_box())

    def test_an_inverted_box_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            BoundingBox(x1=50, y1=50, x2=10, y2=10)

    def test_box_area_is_derived_from_its_corners(self) -> None:
        assert _box().area == 40 * 80


class TestRegistry:
    def test_the_default_detector_is_available(self) -> None:
        assert "hog_person" in available_detectors()

    def test_an_unknown_detector_name_is_rejected(self) -> None:
        with pytest.raises(UnknownDetectorError):
            build_detector("definitely-not-a-detector", DetectorConfig())

    def test_a_detector_is_built_from_config(self) -> None:
        detector = build_detector("hog_person", DetectorConfig(confidence_threshold=0.7))
        assert detector.name == "hog_person"


class TestHogPersonDetector:
    def test_an_empty_frame_yields_no_detections(self) -> None:
        detector = HogPersonDetector(DetectorConfig())
        frame = np.zeros((240, 320, 3), dtype=np.uint8)

        assert detector.detect(frame) == []

    def test_a_zero_sized_frame_is_handled(self) -> None:
        detector = HogPersonDetector(DetectorConfig())
        assert detector.detect(np.zeros((0, 0, 3), dtype=np.uint8)) == []

    def test_a_grayscale_frame_is_accepted(self) -> None:
        detector = HogPersonDetector(DetectorConfig())
        frame = np.full((240, 320), 128, dtype=np.uint8)

        assert isinstance(detector.detect(frame), list)

    def test_a_cuda_device_without_a_gpu_fails_loudly(self) -> None:
        # The test environment has no CUDA device; the detector must say so
        # rather than silently falling back and reporting success.
        import cv2

        if hasattr(cv2, "cuda") and cv2.cuda.getCudaEnabledDeviceCount() > 0:
            pytest.skip("a CUDA device is present in this environment")

        with pytest.raises(CudaUnavailableError):
            HogPersonDetector(DetectorConfig(device="cuda"))


class TestConfidenceFiltering:
    def test_high_thresholds_cannot_increase_detections(self) -> None:
        frame = np.full((240, 320, 3), 100, dtype=np.uint8)
        permissive = HogPersonDetector(DetectorConfig(confidence_threshold=0.0))
        strict = HogPersonDetector(DetectorConfig(confidence_threshold=0.99))

        assert len(strict.detect(frame)) <= len(permissive.detect(frame))


def _box() -> BoundingBox:
    return BoundingBox(x1=10, y1=10, x2=50, y2=90)
