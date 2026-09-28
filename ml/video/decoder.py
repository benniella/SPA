from __future__ import annotations

from collections.abc import Iterator
from types import TracebackType
from typing import Protocol, runtime_checkable

from ml.video.types import DecodedFrame, VideoMetadata


@runtime_checkable
class FrameSampler(Protocol):
    """Decides which frame indices a pipeline should run inference on."""

    def indices(self, *, frame_count: int) -> Iterator[int]: ...


@runtime_checkable
class VideoDecoder(Protocol):
    """Sequential access to a video's frames.

    A decoder is a context manager so its underlying handle is always released,
    including on a processing failure part-way through a video. Frames are
    yielded one at a time: no implementation may load a whole video into memory.
    """

    def __enter__(self) -> VideoDecoder: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    @property
    def metadata(self) -> VideoMetadata: ...

    def frames(self, indices: Iterator[int] | None = None) -> Iterator[DecodedFrame]: ...
