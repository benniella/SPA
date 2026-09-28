from __future__ import annotations

from collections.abc import Iterator


class FixedIntervalSampler:
    """Samples every Nth frame: 0, N, 2N, ...

    Deterministic by construction so two runs over the same video produce the
    same sampled frames, which is what makes tracking output reproducible.
    """

    def __init__(self, interval: int) -> None:
        if interval < 1:
            raise ValueError("Frame interval must be at least 1.")
        self._interval = interval

    @property
    def interval(self) -> int:
        return self._interval

    def indices(self, *, frame_count: int) -> Iterator[int]:
        if frame_count <= 0:
            return
        yield from range(0, frame_count, self._interval)
