from __future__ import annotations

from collections.abc import Callable

from ml.detection.detector import Detector, DetectorConfig
from ml.detection.hog import HogPersonDetector

DetectorFactory = Callable[[DetectorConfig], Detector]

_REGISTRY: dict[str, DetectorFactory] = {
    "hog_person": HogPersonDetector,
}


def available_detectors() -> frozenset[str]:
    return frozenset(_REGISTRY)


def build_detector(name: str, config: DetectorConfig) -> Detector:
    """Resolve a detector by name.

    Only names in the registry can be built, so a misconfigured or
    client-influenced value can never cause arbitrary code to run in the worker.
    """
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise UnknownDetectorError(name) from None
    return factory(config)


class UnknownDetectorError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(
            f"Unknown detector {name!r}. Available: {sorted(_REGISTRY)}."
        )
        self.name = name
