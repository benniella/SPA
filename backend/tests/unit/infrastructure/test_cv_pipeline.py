"""CV processing pipeline tests.

The pipeline is exercised against a fake detector and tracker, so the assertions
are about orchestration — run lifecycle, persistence, failure handling — rather
than about model accuracy, which cannot be asserted from a unit test.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from ml.detection.types import BoundingBox, Detection
from ml.tests.conftest import write_video
from tests.unit.application.fakes import UnitOfWorkStub

from app.application.ports.processing import ProcessingContext
from app.core.config import Settings
from app.core.errors import ProcessingFailedError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.shared import AnalysisRunId, OrganizationId, VideoId, new_id
from app.domain.videos.entities import Video
from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline


class RecordingReporter:
    def __init__(self) -> None:
        self.reports: list[float] = []

    async def report(self, percent: float) -> None:
        self.reports.append(percent)


class ScriptedDetector:
    def __init__(self, *, per_frame: int = 2) -> None:
        self._per_frame = per_frame

    @property
    def name(self) -> str:
        return "scripted"

    def detect(self, frame: object) -> list[Detection]:
        return [
            Detection(
                class_id=0,
                label="person",
                confidence=0.9,
                box=BoundingBox(x1=float(i * 50), y1=10, x2=float(i * 50 + 40), y2=100),
            )
            for i in range(self._per_frame)
        ]


class FakeStorage:
    """A storage adapter that resolves a key to a path on disk."""

    def __init__(self, root: Path, size_bytes: int) -> None:
        self._root = root
        self._size = size_bytes
        self.path = root

    def path_for(self, key: str) -> Path:
        return self._root

    async def stat(self, key: str) -> object:
        from app.application.ports.video_storage import StoredObject

        return StoredObject(key=key, size_bytes=self._size)

    async def delete(self, key: str) -> None:
        return None

    async def open(self, key: str) -> bytes:
        return b""

    def build_key(self, organization_id: str, **kwargs: object) -> str:
        return "key"

    async def presign_upload(self, key: str, **kwargs: object) -> str:
        return "url"

    async def presign_download(self, key: str, **kwargs: object) -> str:
        return "url"


def make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+psycopg://spa:spa@localhost/spa",
        "session_secret": "x" * 40,
        "cv_frame_interval": 5,
        "cv_track_batch_size": 3,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


async def seed_run(
    uow: UnitOfWorkStub, *, organization_id: OrganizationId, video_id: VideoId
) -> AnalysisRun:
    run = AnalysisRun(
        organization_id=organization_id,
        video_id=video_id,
        pipeline=default_pipeline(),
    )
    run.queue()
    await uow.analysis_runs.add(run)
    return run


def build_context(
    run_id: AnalysisRunId, organization_id: OrganizationId, video_id: VideoId
) -> ProcessingContext:
    return ProcessingContext(
        job_id=str(new_id()),
        organization_id=str(organization_id),
        video_id=str(video_id),
        storage_key="org/videos/clip.mp4",
        content_type="video/mp4",
        size_bytes=None,
        analysis_run_id=str(run_id),
    )


class TestSuccessfulProcessing:
    async def test_persists_tracks_and_completes_the_run(self, tmp_path: Path) -> None:
        video_path = write_video(tmp_path / "clip.mp4", frames=20)
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = Video(
            organization_id=organization_id,
            original_filename="clip.mp4",
            storage_key="org/videos/clip.mp4",
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        await uow.videos.add(video)
        run = await seed_run(uow, organization_id=organization_id, video_id=video.id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(),
            storage=FakeStorage(video_path, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(),
        )
        reporter = RecordingReporter()

        outcome = await pipeline.run(build_context(run.id, organization_id, video.id), reporter)

        assert outcome.progress_percent == 100.0
        assert reporter.reports[-1] == 100.0
        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        assert str(stored.status) == "succeeded"
        assert stored.stage_results["detection"]["detections"] == 8
        assert stored.stage_results["tracking"]["track_ids"] == 2

    async def test_tracks_are_persisted_in_bounded_batches(self, tmp_path: Path) -> None:
        video_path = write_video(tmp_path / "clip.mp4", frames=20)
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = Video(
            organization_id=organization_id,
            original_filename="clip.mp4",
            storage_key="key",
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        await uow.videos.add(video)
        run = await seed_run(uow, organization_id=organization_id, video_id=video.id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(cv_frame_interval=1, cv_track_batch_size=4),
            storage=FakeStorage(video_path, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(per_frame=2),
        )

        await pipeline.run(build_context(run.id, organization_id, video.id), RecordingReporter())

        batches = uow.track_observations.batches
        assert batches, "observations must be persisted"
        assert max(batches) <= 4

    async def test_a_dataset_records_the_run_and_video(self, tmp_path: Path) -> None:
        video_path = write_video(tmp_path / "clip.mp4", frames=20)
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = Video(
            organization_id=organization_id,
            original_filename="clip.mp4",
            storage_key="key",
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        await uow.videos.add(video)
        run = await seed_run(uow, organization_id=organization_id, video_id=video.id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(),
            storage=FakeStorage(video_path, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(),
        )
        await pipeline.run(build_context(run.id, organization_id, video.id), RecordingReporter())

        datasets = await uow.tracking_datasets.list_for_run(run.id)
        assert len(datasets) == 1
        assert datasets[0].video_id == video.id
        assert datasets[0].provenance["detector"] == "hog_person"


class TestFailure:
    async def test_a_missing_object_fails_without_touching_the_run(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run(uow, organization_id=organization_id, video_id=video_id)

        class MissingStorage(FakeStorage):
            async def stat(self, key: str) -> object:
                return None

        pipeline = CvProcessingPipeline(
            settings=make_settings(),
            storage=MissingStorage(Path("/nonexistent"), 0),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(),
        )

        with pytest.raises(ProcessingFailedError):
            await pipeline.run(
                build_context(run.id, organization_id, video_id), RecordingReporter()
            )

    async def test_a_decode_failure_marks_the_run_failed(self, tmp_path: Path) -> None:
        corrupt = tmp_path / "corrupt.mp4"
        corrupt.write_bytes(b"not a video")
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run(uow, organization_id=organization_id, video_id=video_id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(),
            storage=FakeStorage(corrupt, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(),
        )

        with pytest.raises(ProcessingFailedError):
            await pipeline.run(
                build_context(run.id, organization_id, video_id), RecordingReporter()
            )

        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        assert str(stored.status) == "failed"
        assert stored.error_message

    async def test_an_unknown_detector_fails_the_run(self, tmp_path: Path) -> None:
        video_path = write_video(tmp_path / "clip.mp4", frames=10)
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run(uow, organization_id=organization_id, video_id=video_id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(cv_detector="not-a-detector"),
            storage=FakeStorage(video_path, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
        )

        with pytest.raises(ProcessingFailedError):
            await pipeline.run(
                build_context(run.id, organization_id, video_id), RecordingReporter()
            )

        stored = await uow.analysis_runs.get(run.id)
        assert stored is not None
        assert str(stored.status) == "failed"

    async def test_a_run_for_another_organization_is_refused(self, tmp_path: Path) -> None:
        video_path = write_video(tmp_path / "clip.mp4", frames=10)
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        video_id = VideoId(new_id())
        run = await seed_run(uow, organization_id=owner, video_id=video_id)

        pipeline = CvProcessingPipeline(
            settings=make_settings(),
            storage=FakeStorage(video_path, 1024),
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            detector=ScriptedDetector(),
        )
        foreign = build_context(run.id, OrganizationId(new_id()), video_id)

        with pytest.raises(ProcessingFailedError):
            await pipeline.run(foreign, RecordingReporter())
