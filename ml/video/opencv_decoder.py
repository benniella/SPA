from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

import cv2
import numpy as np
import numpy.typing as npt

from ml.video.types import DecodedFrame, VideoDecodeError, VideoMetadata


class OpenCvVideoDecoder:
    """Sequential frame access backed by OpenCV's 'VideoCapture'.

    Frames are read one at a time and never accumulated, so memory stays flat
    regardless of video length. When a set of frame indices is supplied, the
    decoder seeks to each in turn rather than decoding and discarding every
    intervening frame.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._capture: cv2.VideoCapture | None = None
        self._metadata: VideoMetadata | None = None

    def __enter__(self) -> OpenCvVideoDecoder:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def open(self) -> None:
        if self._capture is not None:
            return
        if not self._path.is_file():
            raise VideoDecodeError(f"No video file exists at {self._path}.")
        capture = cv2.VideoCapture(str(self._path))
        if not capture.isOpened():
            capture.release()
            raise VideoDecodeError("The video could not be opened; the codec may be unsupported.")
        self._capture = capture
        self._metadata = self._read_metadata(capture)

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None

    @property
    def metadata(self) -> VideoMetadata:
        if self._metadata is None:
            raise VideoDecodeError("The decoder is not open.")
        return self._metadata

    def frames(self, indices: Iterator[int] | None = None) -> Iterator[DecodedFrame]:
        capture = self._require_capture()
        metadata = self.metadata
        requested = list(indices) if indices is not None else None

        if requested is None:
            yield from self._sequential_frames(capture, metadata)
            return

        previous = -1
        for index in requested:
            if index < 0:
                continue
            if index < previous:
                raise VideoDecodeError("Frame indices must be requested in ascending order.")
            frame = self._read_at(capture, index)
            previous = index
            if frame is None:
                break
            yield frame

    def _sequential_frames(
        self, capture: cv2.VideoCapture, metadata: VideoMetadata
    ) -> Iterator[DecodedFrame]:
        index = 0
        while True:
            ok, data = capture.read()
            if not ok or data is None:
                break
            yield _to_frame(data, index=index, metadata=metadata)
            index += 1

    def _read_at(self, capture: cv2.VideoCapture, index: int) -> DecodedFrame | None:
        capture.set(cv2.CAP_PROP_POS_FRAMES, float(index))
        ok, data = capture.read()
        if not ok or data is None:
            return None
        return _to_frame(data, index=index, metadata=self.metadata)

    def _require_capture(self) -> cv2.VideoCapture:
        if self._capture is None:
            raise VideoDecodeError("The decoder is not open.")
        return self._capture

    @staticmethod
    def _read_metadata(capture: cv2.VideoCapture) -> VideoMetadata:
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if width <= 0 or height <= 0:
            capture.release()
            raise VideoDecodeError("The video reports no usable frame dimensions.")

        raw_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        fps = raw_fps if raw_fps > 0 else None

        raw_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        frame_count = raw_count if raw_count > 0 else None

        duration = None
        if fps is not None and frame_count is not None:
            duration = frame_count / fps

        return VideoMetadata(
            width=width,
            height=height,
            fps=fps,
            frame_count=frame_count,
            duration_seconds=duration,
        )


def _to_frame(
    data: npt.NDArray[np.generic], *, index: int, metadata: VideoMetadata
) -> DecodedFrame:
    timestamp = index / metadata.fps if metadata.fps else 0.0
    return DecodedFrame(
        index=index,
        timestamp_seconds=timestamp,
        width=int(data.shape[1]),
        height=int(data.shape[0]),
        data=np.asarray(data),
    )
