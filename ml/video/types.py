from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


@dataclass(frozen=True, slots=True)
class VideoMetadata:
    """Source media characteristics read from a video container.

    'fps' and 'frame_count' are optional because containers do not always
    report them reliably; a caller that needs a duration must fall back to
    'duration_seconds', and a caller that needs a frame count must decide what to
    do when it is unknown rather than trusting a fabricated value.
    """

    width: int
    height: int
    fps: float | None
    frame_count: int | None
    duration_seconds: float | None

    @property
    def has_reliable_frame_count(self) -> bool:
        return self.frame_count is not None and self.frame_count > 0


@dataclass(frozen=True, slots=True)
class DecodedFrame:
    """One frame read from a video, with the position it was read at."""

    index: int
    timestamp_seconds: float
    width: int
    height: int
    #: A decoded image array. Typed as a plain ndarray because the OpenCV stubs
    #: do not narrow the dtype of a captured frame.
    data: npt.NDArray[np.integer | np.floating]


class VideoDecodeError(RuntimeError):
    """The video could not be opened or read.

    Raised for a missing file, an unsupported codec, or a container that yields
    no frames — all conditions the worker must surface as a processing failure
    rather than retry forever.
    """
