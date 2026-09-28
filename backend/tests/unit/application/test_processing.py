"""Processing use-case tests.

The assertions that matter: an incomplete upload cannot be processed, a repeated
request does not create a second job, and no call crosses an organization
boundary.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.ports.jobs import Job, JobResult
from app.application.use_cases.processing import (
    get_processing_job,
    get_video_processing_state,
    request_video_processing,
)
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.organizations.entities import MembershipRole
from app.domain.shared import JobId, OrganizationId, VideoId, new_id
from app.domain.videos.entities import Video, VideoStatus
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.application.test_videos import seed_member


class RecordingDispatcher:
    """Records dispatches and persists a job, like the real dispatcher."""

    def __init__(self, uow: UnitOfWorkStub) -> None:
        self.jobs: list[Job] = []
        self._uow = uow

    async def dispatch(self, job: Job) -> JobResult:
        self.jobs.append(job)
        persisted = ProcessingJob(
            organization_id=OrganizationId(uuid.UUID(str(job.organization_id))),
            video_id=VideoId(uuid.UUID(str(job.payload["video_id"]))),
            job_type=str(job.kind),
            max_attempts=job.max_attempts,
        )
        await self._uow.processing_jobs.add(persisted)
        return JobResult(accepted=True, job_id=str(persisted.id))


async def seed_video(
    uow: UnitOfWorkStub,
    organization_id: OrganizationId,
    *,
    uploaded: bool = True,
) -> Video:
    video = Video(
        organization_id=organization_id,
        original_filename="match.mp4",
        storage_key=f"{organization_id}/videos/match.mp4",
    )
    if uploaded:
        video.mark_uploaded(size_bytes=4096, content_type="video/mp4")
    await uow.videos.add(video)
    return video


class TestRequestProcessing:
    async def test_queues_a_job_for_an_uploaded_video(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await seed_video(uow, organization_id)
        dispatcher = RecordingDispatcher(uow)

        job = await request_video_processing(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            dispatcher=dispatcher,
        )

        assert job.status == JobStatus.QUEUED
        assert len(dispatcher.jobs) == 1
        assert dispatcher.jobs[0].payload == {"video_id": str(video.id)}

    async def test_does_not_mark_the_video_processed_on_queueing(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await seed_video(uow, organization_id)

        await request_video_processing(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            dispatcher=RecordingDispatcher(uow),
        )

        # Queueing is not completion: the state must not claim otherwise.
        assert video.status == VideoStatus.UPLOADED

    async def test_a_repeated_request_returns_the_existing_job(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await seed_video(uow, organization_id)
        dispatcher = RecordingDispatcher(uow)

        first = await request_video_processing(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            dispatcher=dispatcher,
        )
        second = await request_video_processing(
            uow,
            organization_id=organization_id,
            user_id=user.id,
            video_id=video.id,
            dispatcher=dispatcher,
        )

        assert first.id == second.id
        assert len(dispatcher.jobs) == 1

    async def test_refuses_a_video_whose_upload_never_completed(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)
        video = await seed_video(uow, organization_id, uploaded=False)
        dispatcher = RecordingDispatcher(uow)

        with pytest.raises(ConflictError):
            await request_video_processing(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=video.id,
                dispatcher=dispatcher,
            )
        assert dispatcher.jobs == []

    async def test_unknown_video_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user = await seed_member(uow, organization_id)

        with pytest.raises(NotFoundError):
            await request_video_processing(
                uow,
                organization_id=organization_id,
                user_id=user.id,
                video_id=VideoId(new_id()),
                dispatcher=RecordingDispatcher(uow),
            )

    async def test_cross_tenant_request_looks_like_not_found(self) -> None:
        uow = UnitOfWorkStub()
        owner_organization = OrganizationId(new_id())
        attacker_organization = OrganizationId(new_id())
        attacker = await seed_member(uow, attacker_organization)
        video = await seed_video(uow, owner_organization)
        dispatcher = RecordingDispatcher(uow)

        with pytest.raises(NotFoundError):
            await request_video_processing(
                uow,
                organization_id=attacker_organization,
                user_id=attacker.id,
                video_id=video.id,
                dispatcher=dispatcher,
            )
        assert dispatcher.jobs == []

    async def test_a_read_only_member_cannot_request_processing(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        viewer = await seed_member(uow, organization_id, role=MembershipRole.VIEWER)
        video = await seed_video(uow, organization_id)
        dispatcher = RecordingDispatcher(uow)

        with pytest.raises(PermissionDeniedError):
            await request_video_processing(
                uow,
                organization_id=organization_id,
                user_id=viewer.id,
                video_id=video.id,
                dispatcher=dispatcher,
            )
        assert dispatcher.jobs == []


class TestGetProcessingJob:
    async def test_returns_a_job_in_the_callers_organization(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        job = ProcessingJob(
            organization_id=organization_id,
            video_id=VideoId(new_id()),
            job_type="ingest_video",
        )
        await uow.processing_jobs.add(job)

        found = await get_processing_job(uow, organization_id=organization_id, job_id=JobId(job.id))
        assert found.id == job.id

    async def test_cross_tenant_job_access_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        job = ProcessingJob(
            organization_id=OrganizationId(new_id()),
            video_id=VideoId(new_id()),
            job_type="ingest_video",
        )
        await uow.processing_jobs.add(job)

        with pytest.raises(NotFoundError):
            await get_processing_job(
                uow,
                organization_id=OrganizationId(new_id()),
                job_id=JobId(job.id),
            )


class TestVideoProcessingState:
    async def test_reports_the_latest_job(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = await seed_video(uow, organization_id)
        job = ProcessingJob(
            organization_id=organization_id,
            video_id=video.id,
            job_type="ingest_video",
        )
        await uow.processing_jobs.add(job)

        state = await get_video_processing_state(
            uow, organization_id=organization_id, video_id=video.id
        )
        assert state.video_status == "uploaded"
        assert state.job is not None
        assert state.job.id == job.id

    async def test_cross_tenant_state_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        video = await seed_video(uow, OrganizationId(new_id()))

        with pytest.raises(NotFoundError):
            await get_video_processing_state(
                uow,
                organization_id=OrganizationId(new_id()),
                video_id=video.id,
            )

    async def test_reports_cv_counts_once_a_run_has_produced_them(self) -> None:
        from app.domain.analysis.entities import AnalysisRun, default_pipeline

        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = await seed_video(uow, organization_id)
        run = AnalysisRun(
            organization_id=organization_id,
            video_id=video.id,
            pipeline=default_pipeline(),
        )
        run.queue()
        run.start()
        run.stage_results["detection"] = {"frames_sampled": 12, "detections": 30}
        run.stage_results["tracking"] = {"tracks": 28, "track_ids": 5}
        await uow.analysis_runs.add(run)

        state = await get_video_processing_state(
            uow, organization_id=organization_id, video_id=video.id
        )

        assert state.frames_processed == 12
        assert state.detections == 30
        assert state.tracks == 5

    async def test_cv_counts_are_absent_before_a_run_exists(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        video = await seed_video(uow, organization_id)

        state = await get_video_processing_state(
            uow, organization_id=organization_id, video_id=video.id
        )

        assert state.detections is None
        assert state.tracks is None
        assert state.frames_processed is None

    async def test_a_run_in_another_organization_is_not_exposed(self) -> None:
        from app.domain.analysis.entities import AnalysisRun, default_pipeline

        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        video = await seed_video(uow, owner)
        other_video = await seed_video(uow, OrganizationId(new_id()))
        run = AnalysisRun(
            organization_id=OrganizationId(new_id()),
            video_id=other_video.id,
            pipeline=default_pipeline(),
        )
        run.queue()
        run.stage_results["tracking"] = {"track_ids": 99}
        await uow.analysis_runs.add(run)

        state = await get_video_processing_state(uow, organization_id=owner, video_id=video.id)

        assert state.analysis_run is None
        assert state.tracks is None
