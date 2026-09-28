from __future__ import annotations

from collections.abc import Callable

from ml.tracking.centroid import CentroidTracker
from ml.tracking.tracker import Tracker, TrackerConfig

TrackerFactory = Callable[[TrackerConfig], Tracker]

_REGISTRY: dict[str, TrackerFactory] = {
    "centroid": CentroidTracker,
}


class UnknownTrackerError(ValueError):
    def __init__(self, name: str) -> None:
        super().__init__(f"Unknown tracker {name!r}. Available: {sorted(_REGISTRY)}.")
        self.name = name


def available_trackers() -> frozenset[str]:
    return frozenset(_REGISTRY)


def build_tracker(name: str, config: TrackerConfig | None = None) -> Tracker:
    try:
        factory = _REGISTRY[name]
    except KeyError:
        raise UnknownTrackerError(name) from None
    return factory(config) if config is not None else factory(TrackerConfig())
