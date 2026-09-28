"""The metric use cases against in-memory fakes.

These assert the authorization and lifecycle rules the API relies on: a
cross-organization run is not found, a run with no tracking data cannot be
calculated, and a repeated request does not create a second job.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.use_cases import metrics as use_cases
from app.application.use_cases.metrics import METRICS_JOB_TYPE
from app.application.use_cases.organizations import require_organization_member
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.metrics.types import MetricAvailability, MetricName, MetricUnit, MetricValue
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.shared import AnalysisRunId, JobId, OrganizationId, Slug, UserId, VideoId, new_id
from app.domain.users.entities import Email, User
from tests.unit.application.fakes import UnitOfWorkStub


class RecordingDispatcher:
    """Records dispatches and persists the job row, as the real dispatcher does."""

    def __init__(self, uow: UnitOfWorkStub | None = None, organization_id: str = "") -> None:
        self.jobs: list[object] = []
        self._uow = uow
        self._organization_id = organization_id

    async def dispatch(self, job: object) -> object:
        from app.application.ports.jobs import JobResult
        from app.domain.jobs.entities import ProcessingJob

        self.jobs.append(job)
        job_id = new_id()
        if self._uow is not None:
            payload = job.payload  # type: ignore[attr-defined]
            await self._uow.processing_jobs.add(
                ProcessingJob(
                    organization_id=OrganizationId(uuid.UUID(self._organization_id)),
                    video_id=VideoId(uuid.UUID(payload["video_id"])),
                    job_type=METRICS_JOB_TYPE,
                    id=JobId(job_id),
                )
            )
        return JobResult(accepted=True, job_id=str(job_id))


async def seed_member(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    role: str = MembershipRole.COACH,
) -> UserId:
    user = User(email=Email(f"{new_id()}@example.com"), display_name="Coach")
    await uow.users.add(user)
    await uow.organizations.add(
        Organization(
            name="Metrics FC", slug=Slug(f"metrics-{new_id().hex[:8]}"), id=organization_id
        )
    )
    uow.organizations.memberships.append(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=MembershipRole(role),
        )
    )
    return user.id


async def seed_run(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    status: str,
) -> AnalysisRun:
    run = AnalysisRun(
        organization_id=organization_id,
        video_id=VideoId(new_id()),
        pipeline=default_pipeline(),
    )
    if status == "queued":
        run.queue()
    elif status == "running":
        run.queue()
        run.start()
    elif status == "succeeded":
        run.queue()
        run.start()
        run.succeed()
    elif status == "failed":
        run.queue()
        run.start()
        run.fail("decode failed")
    await uow.analysis_runs.add(run)
    return run


class TestRequestMetricsCalculation:
    async def test_a_succeeded_run_is_queued(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        dispatcher = RecordingDispatcher(uow, str(organization_id))

        request = await use_cases.request_metrics_calculation(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )

        assert request.analysis_run_id == run.id
        assert len(dispatcher.jobs) == 1

    async def test_a_repeated_request_reuses_the_active_job(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        dispatcher = RecordingDispatcher(uow, str(organization_id))

        first = await use_cases.request_metrics_calculation(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )
        second = await use_cases.request_metrics_calculation(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )

        assert first.job.id == second.job.id
        assert len(dispatcher.jobs) == 1

    async def test_a_run_without_tracking_data_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="queued")

        with pytest.raises(ConflictError):
            await use_cases.request_metrics_calculation(
                uow,
                organization_id=organization_id,
                user_id=user_id,
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )

    async def test_a_cross_organization_run_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        other = OrganizationId(new_id())
        await seed_member(uow, organization_id=other)
        user_id = await seed_member(uow, organization_id=other)
        run = await seed_run(uow, organization_id=owner, status="succeeded")

        with pytest.raises(NotFoundError):
            await use_cases.request_metrics_calculation(
                uow,
                organization_id=other,
                user_id=user_id,
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )

    async def test_a_non_member_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")

        with pytest.raises(NotFoundError):
            await use_cases.request_metrics_calculation(
                uow,
                organization_id=organization_id,
                user_id=UserId(new_id()),
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )


class TestGetAnalysisMetrics:
    async def test_reads_the_persisted_metrics_grouped_by_track(self) -> None:
        from app.domain.metrics.types import TrackMetricRecord

        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")

        await uow.track_metrics.replace_for_run(
            run.id,
            [
                TrackMetricRecord(
                    organization_id=organization_id,
                    analysis_run_id=run.id,
                    track_id=7,
                    value=MetricValue.available(
                        MetricName.DISPLACEMENT, MetricUnit.PIXELS, 1832.4, sample_count=12
                    ),
                ),
                TrackMetricRecord(
                    organization_id=organization_id,
                    analysis_run_id=run.id,
                    track_id=7,
                    value=MetricValue.unavailable(
                        MetricName.PEAK_SPEED, MetricUnit.PIXELS_PER_SECOND
                    ),
                ),
            ],
        )

        metrics = await use_cases.get_analysis_metrics(
            uow, organization_id=organization_id, user_id=user_id, run_id=run.id
        )

        assert len(metrics.tracks) == 1
        assert metrics.tracks[0].track_id == 7
        displacement = metrics.tracks[0].value_for(MetricName.DISPLACEMENT)
        assert displacement is not None
        assert displacement.value == pytest.approx(1832.4)
        peak = metrics.tracks[0].value_for(MetricName.PEAK_SPEED)
        assert peak is not None
        assert peak.availability is MetricAvailability.UNAVAILABLE
        assert peak.value is None

    async def test_a_run_with_no_metrics_is_a_conflict(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="queued")

        with pytest.raises(ConflictError):
            await use_cases.get_analysis_metrics(
                uow, organization_id=organization_id, user_id=user_id, run_id=run.id
            )

    async def test_a_cross_organization_run_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        other = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=other)
        run = await seed_run(uow, organization_id=owner, status="succeeded")

        with pytest.raises(NotFoundError):
            await use_cases.get_analysis_metrics(
                uow, organization_id=other, user_id=user_id, run_id=run.id
            )

    async def test_metrics_cannot_cross_contaminate_between_runs(self) -> None:
        from app.domain.metrics.types import TrackMetricRecord

        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        first = await seed_run(uow, organization_id=organization_id, status="succeeded")
        second = await seed_run(uow, organization_id=organization_id, status="succeeded")

        for run, value in ((first, 10.0), (second, 99.0)):
            await uow.track_metrics.replace_for_run(
                run.id,
                [
                    TrackMetricRecord(
                        organization_id=organization_id,
                        analysis_run_id=run.id,
                        track_id=1,
                        value=MetricValue.available(
                            MetricName.DISPLACEMENT, MetricUnit.PIXELS, value, sample_count=2
                        ),
                    )
                ],
            )

        first_metrics = await use_cases.get_analysis_metrics(
            uow, organization_id=organization_id, user_id=user_id, run_id=first.id
        )
        second_metrics = await use_cases.get_analysis_metrics(
            uow, organization_id=organization_id, user_id=user_id, run_id=second.id
        )

        assert first_metrics.tracks[0].value_for(MetricName.DISPLACEMENT).value == pytest.approx(
            10.0
        )
        assert second_metrics.tracks[0].value_for(MetricName.DISPLACEMENT).value == pytest.approx(
            99.0
        )


class TestAuthorizationHelper:
    async def test_a_viewer_may_read_but_a_non_member_may_not(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        viewer = await seed_member(uow, organization_id=organization_id, role=MembershipRole.VIEWER)

        membership = await require_organization_member(
            uow, organization_id=organization_id, user_id=viewer
        )
        assert membership.user_id == viewer

        with pytest.raises(NotFoundError):
            await require_organization_member(
                uow, organization_id=organization_id, user_id=UserId(new_id())
            )


def test_run_ids_are_typed() -> None:
    assert AnalysisRunId(new_id()) is not None
