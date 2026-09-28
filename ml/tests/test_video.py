from __future__ import annotations

from pathlib import Path

import pytest

from ml.tests.conftest import write_video
from ml.video.opencv_decoder import OpenCvVideoDecoder
from ml.video.sampling import FixedIntervalSampler
from ml.video.types import VideoDecodeError


class TestMetadata:
    def test_reads_dimensions_and_frame_rate(self, synthetic_video: Path) -> None:
        with OpenCvVideoDecoder(synthetic_video) as decoder:
            metadata = decoder.metadata

        assert metadata.width == 320
        assert metadata.height == 240
        assert metadata.fps == pytest.approx(10.0, rel=0.1)
        assert metadata.frame_count == 20
        assert metadata.duration_seconds == pytest.approx(2.0, rel=0.1)
        assert metadata.has_reliable_frame_count is True


class TestFrameIteration:
    def test_yields_every_frame_in_order(self, synthetic_video: Path) -> None:
        with OpenCvVideoDecoder(synthetic_video) as decoder:
            indices = [frame.index for frame in decoder.frames()]

        assert indices == list(range(20))

    def test_seeks_to_requested_indices_only(self, synthetic_video: Path) -> None:
        with OpenCvVideoDecoder(synthetic_video) as decoder:
            frames = list(decoder.frames(iter([0, 5, 10, 15])))

        assert [frame.index for frame in frames] == [0, 5, 10, 15]

    def test_an_out_of_order_request_is_rejected(self, synthetic_video: Path) -> None:
        with OpenCvVideoDecoder(synthetic_video) as decoder, pytest.raises(VideoDecodeError):
            list(decoder.frames(iter([5, 2])))

    def test_timestamps_follow_the_frame_rate(self, synthetic_video: Path) -> None:
        with OpenCvVideoDecoder(synthetic_video) as decoder:
            frames = list(decoder.frames(iter([0, 10])))

        assert frames[0].timestamp_seconds == pytest.approx(0.0)
        assert frames[1].timestamp_seconds == pytest.approx(1.0, rel=0.1)


class TestSampling:
    def test_samples_at_a_fixed_interval(self) -> None:
        assert list(FixedIntervalSampler(5).indices(frame_count=12)) == [0, 5, 10]

    def test_interval_of_one_keeps_every_frame(self) -> None:
        assert list(FixedIntervalSampler(1).indices(frame_count=3)) == [0, 1, 2]

    def test_an_empty_video_yields_no_indices(self) -> None:
        assert list(FixedIntervalSampler(5).indices(frame_count=0)) == []

    def test_an_interval_below_one_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            FixedIntervalSampler(0)


class TestInvalidVideo:
    def test_a_missing_file_is_a_decode_error(self, tmp_path: Path) -> None:
        with pytest.raises(VideoDecodeError):
            OpenCvVideoDecoder(tmp_path / "absent.mp4").open()

    def test_a_non_video_file_is_a_decode_error(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"this is not a video container")

        with pytest.raises(VideoDecodeError):
            OpenCvVideoDecoder(corrupt).open()

    def test_the_handle_is_released_after_use(self, synthetic_video: Path) -> None:
        decoder = OpenCvVideoDecoder(synthetic_video)
        decoder.open()
        decoder.close()

        # Metadata read at open time is still readable, but reading frames from a
        # released decoder must fail rather than silently return nothing.
        with pytest.raises(VideoDecodeError):
            list(decoder.frames())


class TestResourceBoundaries:
    def test_frames_are_streamed_not_accumulated(self, synthetic_video: Path) -> None:
        write_video(synthetic_video, frames=200)
        with OpenCvVideoDecoder(synthetic_video) as decoder:
            stream = decoder.frames()
            first = next(stream)

            # A generator, not a list: the whole video is never materialised.
            assert first.index == 0
            assert not isinstance(stream, list)
