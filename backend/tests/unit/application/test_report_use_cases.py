"""The report use cases against in-memory fakes.

These assert the authorization and lifecycle rules the API relies on: a report
can only be requested for a finished run, a repeated request reuses the report
covering that run, and a cross-organization run is not found.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.use_cases import reports as use_cases
from app.application.use_cases.reports import REPORT_JOB_TYPE
from app.core.errors import ConflictError, NotFoundError
from app.domain.analysis.entities import AnalysisRun, default_pipeline
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.reports.entities import ReportStatus
from app.domain.shared import (
    AnalysisRunId,
    JobId,
    OrganizationId,
    Slug,
    UserId,
    VideoId,
    new_id,
)
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
                    job_type=REPORT_JOB_TYPE,
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
            name="Reports FC", slug=Slug(f"reports-{new_id().hex[:8]}"), id=organization_id
        )
    )
    uow.organizations.memberships.append(
        OrganizationMembership(
            organization_id=organization_id, user_id=user.id, role=MembershipRole(role)
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
    elif status == "partially_succeeded":
        run.queue()
        run.start()
        run.succeed(partial=True)
    elif status == "failed":
        run.queue()
        run.start()
        run.fail("decode failed")
    await uow.analysis_runs.add(run)
    return run


class TestRequestRunReport:
    async def test_a_succeeded_run_is_queued(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        dispatcher = RecordingDispatcher(uow, str(organization_id))

        report = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )

        assert report.scope.analysis_run_ids == (run.id,)
        assert report.status == ReportStatus.GENERATING
        assert report.created_by_id == user_id
        assert len(dispatcher.jobs) == 1

    async def test_a_partially_succeeded_run_is_reportable(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="partially_succeeded")

        report = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=RecordingDispatcher(uow, str(organization_id)),
        )

        assert report.status == ReportStatus.GENERATING

    async def test_a_run_still_processing_is_refused(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="running")

        with pytest.raises(ConflictError):
            await use_cases.request_run_report(
                uow,
                organization_id=organization_id,
                user_id=user_id,
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )

    async def test_a_repeated_request_reuses_the_existing_report(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        dispatcher = RecordingDispatcher(uow, str(organization_id))

        first = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )
        second = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )

        assert first.id == second.id
        assert len(dispatcher.jobs) == 1

    async def test_a_ready_report_is_returned_unchanged(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        dispatcher = RecordingDispatcher(uow, str(organization_id))

        first = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )
        first.mark_ready()
        await uow.reports.update(first)

        second = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=dispatcher,
        )

        assert second.status == ReportStatus.READY
        assert len(dispatcher.jobs) == 1

    async def test_a_cross_organization_run_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        owner = OrganizationId(new_id())
        other = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=other)
        run = await seed_run(uow, organization_id=owner, status="succeeded")

        with pytest.raises(NotFoundError):
            await use_cases.request_run_report(
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
            await use_cases.request_run_report(
                uow,
                organization_id=organization_id,
                user_id=UserId(new_id()),
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )

    async def test_a_read_only_member_cannot_create_a_report(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(
            uow, organization_id=organization_id, role=MembershipRole.VIEWER
        )
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")

        from app.core.errors import PermissionDeniedError

        with pytest.raises(PermissionDeniedError):
            await use_cases.request_run_report(
                uow,
                organization_id=organization_id,
                user_id=user_id,
                run_id=run.id,
                dispatcher=RecordingDispatcher(),
            )


class TestReadReports:
    async def test_get_resolves_within_the_organization(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        report = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=RecordingDispatcher(uow, str(organization_id)),
        )

        found = await use_cases.get_report(
            uow, organization_id=organization_id, report_id=report.id
        )

        assert found.id == report.id

    async def test_get_of_another_organizations_report_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        other = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        report = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=RecordingDispatcher(uow, str(organization_id)),
        )

        with pytest.raises(NotFoundError):
            await use_cases.get_report(uow, organization_id=other, report_id=report.id)

    async def test_a_run_report_is_found_by_the_run_alone(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        report = await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=RecordingDispatcher(uow, str(organization_id)),
        )

        found = await use_cases.find_report_for_run(
            uow, organization_id=organization_id, run_id=run.id
        )

        assert found is not None
        assert found.id == report.id

    async def test_a_run_with_no_report_has_none(self) -> None:
        uow = UnitOfWorkStub()

        found = await use_cases.find_report_for_run(
            uow,
            organization_id=OrganizationId(new_id()),
            run_id=AnalysisRunId(new_id()),
        )

        assert found is None

    async def test_another_organizations_run_has_no_findable_report(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        other = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)
        run = await seed_run(uow, organization_id=organization_id, status="succeeded")
        await use_cases.request_run_report(
            uow,
            organization_id=organization_id,
            user_id=user_id,
            run_id=run.id,
            dispatcher=RecordingDispatcher(uow, str(organization_id)),
        )

        found = await use_cases.find_report_for_run(uow, organization_id=other, run_id=run.id)

        assert found is None
