"""CV processing against real PostgreSQL.

Proves the persistence contract the unit tests cannot: that tracking
observations land in the schema, that the analysis run reaches a terminal state
only after they are written, and that a run's data is scoped to its
organization. The detector is scripted, so this measures persistence and
orchestration, not model accuracy.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


def _write_clip(path: Path, *, frames: int = 20) -> Path:
    import cv2
    import numpy as np

    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (320, 240))
    assert writer.isOpened()
    for index in range(frames):
        frame = np.full((240, 320, 3), 30, dtype=np.uint8)
        left = 10 + index * 5
        cv2.rectangle(frame, (left, 60), (left + 40, 200), (200, 200, 200), -1)
        writer.write(frame)
    writer.release()
    return path


class ScriptedDetector:
    @property
    def name(self) -> str:
        return "scripted"

    def detect(self, frame: object) -> list[object]:
        from ml.detection.types import BoundingBox, Detection

        return [
            Detection(
                class_id=0,
                label="person",
                confidence=0.9,
                box=BoundingBox(x1=20, y1=60, x2=60, y2=200),
            ),
            Detection(
                class_id=0,
                label="person",
                confidence=0.8,
                box=BoundingBox(x1=200, y1=60, x2=240, y2=200),
            ),
        ]


async def _seed_org_and_video(storage_key: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    from app.core.config import get_settings
    from app.domain.analysis.entities import AnalysisRun, default_pipeline
    from app.domain.shared import OrganizationId, VideoId
    from app.domain.videos.entities import Video
    from app.infrastructure.database.engine import get_session_factory
    from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory

    organization_id = uuid.uuid4()
    session_factory = get_session_factory(get_settings())
    uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)

    from app.domain.organizations.entities import Organization
    from app.domain.shared import Slug

    async with uow_factory() as uow:
        await uow.organizations.add(
            Organization(
                name="CV FC",
                slug=Slug(f"cv-fc-{organization_id.hex[:8]}"),
                id=OrganizationId(organization_id),
            )
        )
        video = Video(
            organization_id=OrganizationId(organization_id),
            original_filename="clip.mp4",
            storage_key=storage_key,
            id=VideoId(uuid.uuid4()),
        )
        video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
        await uow.videos.add(video)

        run = AnalysisRun(
            organization_id=OrganizationId(organization_id),
            video_id=video.id,
            pipeline=default_pipeline(),
        )
        run.queue()
        await uow.analysis_runs.add(run)
        await uow.commit()

    return organization_id, uuid.UUID(str(video.id)), uuid.UUID(str(run.id))


class _Storage:
    def __init__(self, path: Path) -> None:
        self._path = path

    def path_for(self, key: str) -> Path:
        return self._path

    async def stat(self, key: str) -> object:
        from app.application.ports.video_storage import StoredObject

        return StoredObject(key=key, size_bytes=1024)


class TestCvPersistence:
    async def test_tracks_are_written_and_the_run_succeeds(self, tmp_path: Path) -> None:
        from app.application.ports.processing import ProcessingContext
        from app.core.config import get_settings
        from app.domain.shared import AnalysisRunId
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
        from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline

        clip = _write_clip(tmp_path / "clip.mp4")
        organization_id, video_id, run_id = await _seed_org_and_video("cv/videos/clip.mp4")

        settings = get_settings()
        session_factory = get_session_factory(settings)
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        pipeline = CvProcessingPipeline(
            settings=settings,
            storage=_Storage(clip),  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
            detector=ScriptedDetector(),  # type: ignore[arg-type]
        )

        context = ProcessingContext(
            job_id=str(uuid.uuid4()),
            organization_id=str(organization_id),
            video_id=str(video_id),
            storage_key="cv/videos/clip.mp4",
            content_type="video/mp4",
            size_bytes=None,
            analysis_run_id=str(run_id),
        )

        class Reporter:
            async def report(self, percent: float) -> None:
                return None

        await pipeline.run(context, Reporter())

        async with uow_factory() as uow:
            run = await uow.analysis_runs.get(AnalysisRunId(run_id))
            assert run is not None
            assert str(run.status) == "succeeded"
            assert run.stage_results["tracking"]["track_ids"] == 2

            count = await uow.track_observations.count_for_run(AnalysisRunId(run_id))
            assert count == 8

            distinct = await uow.track_observations.distinct_track_count(AnalysisRunId(run_id))
            assert distinct == 2

            datasets = await uow.tracking_datasets.list_for_run(AnalysisRunId(run_id))
            assert len(datasets) == 1
            assert datasets[0].object_count == 2

    async def test_tracks_are_scoped_to_their_organization(self, tmp_path: Path) -> None:
        from app.application.ports.processing import ProcessingContext
        from app.core.config import get_settings
        from app.domain.shared import AnalysisRunId
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
        from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline

        clip = _write_clip(tmp_path / "clip.mp4")
        organization_id, video_id, run_id = await _seed_org_and_video("cv/videos/clip2.mp4")
        other_organization = uuid.uuid4()

        settings = get_settings()
        session_factory = get_session_factory(settings)
        uow_factory = SqlAlchemyUnitOfWorkFactory(session_factory)
        pipeline = CvProcessingPipeline(
            settings=settings,
            storage=_Storage(clip),  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
            detector=ScriptedDetector(),  # type: ignore[arg-type]
        )
        context = ProcessingContext(
            job_id=str(uuid.uuid4()),
            organization_id=str(organization_id),
            video_id=str(video_id),
            storage_key="cv/videos/clip2.mp4",
            content_type="video/mp4",
            size_bytes=None,
            analysis_run_id=str(run_id),
        )

        class Reporter:
            async def report(self, percent: float) -> None:
                return None

        await pipeline.run(context, Reporter())

        async with uow_factory() as uow:
            records = await uow.track_observations.list_for_run(AnalysisRunId(run_id))
            assert records
            for record in records:
                assert record.organization_id == organization_id
                assert record.organization_id != other_organization

    async def test_a_run_from_another_organization_is_refused(self, tmp_path: Path) -> None:
        from app.application.ports.processing import ProcessingContext
        from app.core.config import get_settings
        from app.core.errors import ProcessingFailedError
        from app.infrastructure.database.engine import get_session_factory
        from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWorkFactory
        from app.infrastructure.processing.cv_pipeline import CvProcessingPipeline

        clip = _write_clip(tmp_path / "clip.mp4")
        _, video_id, run_id = await _seed_org_and_video("cv/videos/clip3.mp4")

        settings = get_settings()
        uow_factory = SqlAlchemyUnitOfWorkFactory(get_session_factory(settings))
        pipeline = CvProcessingPipeline(
            settings=settings,
            storage=_Storage(clip),  # type: ignore[arg-type]
            uow_factory=uow_factory,  # type: ignore[arg-type]
            detector=ScriptedDetector(),  # type: ignore[arg-type]
        )
        foreign = ProcessingContext(
            job_id=str(uuid.uuid4()),
            organization_id=str(uuid.uuid4()),
            video_id=str(video_id),
            storage_key="cv/videos/clip3.mp4",
            content_type="video/mp4",
            size_bytes=None,
            analysis_run_id=str(run_id),
        )

        class Reporter:
            async def report(self, percent: float) -> None:
                return None

        with pytest.raises(ProcessingFailedError):
            await pipeline.run(foreign, Reporter())
