"""The report export use cases against in-memory fakes.

An export renders a report's stored snapshot and writes it under the
organization's own storage prefix. These assert the authorization, the
ready-state requirement, and that the stored document contains the report's real
data rather than a placeholder.
"""

from __future__ import annotations

import uuid

import pytest

from app.application.use_cases import reports as use_cases
from app.application.use_cases.metrics import group_track_metrics
from app.core.errors import ConflictError, NotFoundError, PermissionDeniedError
from app.domain.metrics.types import (
    MetricName,
    MetricUnit,
    MetricValue,
    TrackMetricRecord,
)
from app.domain.organizations.entities import MembershipRole
from app.domain.reports.builder import build_report_content
from app.domain.reports.content import content_to_dict
from app.domain.reports.entities import Report, ReportScope
from app.domain.shared import OrganizationId, ReportId, new_id
from app.domain.videos.entities import Video
from tests.unit.application.fakes import UnitOfWorkStub
from tests.unit.application.test_report_use_cases import seed_member, seed_run
from tests.unit.application.test_videos import FakeVideoStorage


async def seed_report(
    uow: UnitOfWorkStub,
    *,
    organization_id: OrganizationId,
    role: str = MembershipRole.COACH,
) -> tuple[Report, str, FakeVideoStorage]:
    """A ready report for a succeeded run, with its metrics already persisted.

    The report row is written directly rather than through the request use case,
    so a read-only member can be the caller of the export under test.
    """
    user_id = await seed_member(uow, organization_id=organization_id, role=role)
    run = await seed_run(uow, organization_id=organization_id, status="succeeded")

    video = Video(
        organization_id=organization_id,
        original_filename="match.mp4",
        storage_key=f"reports/{new_id()}.mp4",
    )
    video.mark_uploaded(size_bytes=1024, content_type="video/mp4")
    await uow.videos.add(video)

    records = [
        TrackMetricRecord(
            organization_id=organization_id,
            analysis_run_id=run.id,
            track_id=1,
            value=MetricValue.available(
                MetricName.OBSERVATION_COUNT, MetricUnit.COUNT, 4.0, sample_count=4
            ),
        )
    ]
    await uow.track_metrics.replace_for_run(run.id, records)
    content = build_report_content(
        run=run,
        video=video,
        observation_count=4,
        track_count=1,
        metrics=group_track_metrics(run, records),
    )

    report = Report(
        organization_id=organization_id,
        title="Analysis report",
        scope=ReportScope(analysis_run_ids=(run.id,)),
        created_by_id=user_id,
        content=content_to_dict(content),
    )
    report.mark_ready()
    await uow.reports.add(report)
    await uow.commit()

    return report, str(user_id), FakeVideoStorage()


class TestExportReport:
    async def test_a_ready_report_is_rendered_and_stored(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)

        export = await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        document = await storage.open(export.storage_key)
        assert document != b""
        assert b"SPA \xe2\x80\x94 Sport Performance Analysis" in document
        assert b"match.mp4" in document

    async def test_the_export_is_namespaced_by_organization(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)

        export = await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        assert export.storage_key.startswith(f"{organization_id}/")
        assert "reports" in export.storage_key

    async def test_the_key_is_recorded_on_the_report(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)

        export = await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        stored = await uow.reports.get(report.id)
        assert stored is not None
        assert stored.storage_key == export.storage_key

    async def test_the_same_report_renders_the_same_document(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)

        first = await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )
        first_bytes = await storage.open(first.storage_key)

        second = await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        assert await storage.open(second.storage_key) == first_bytes

    async def test_a_report_that_is_not_ready_cannot_be_exported(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)
        generating = Report(
            organization_id=organization_id,
            title="Analysis report",
            scope=ReportScope(analysis_run_ids=report.scope.analysis_run_ids),
        )
        generating.mark_generating()
        await uow.reports.add(generating)

        with pytest.raises(ConflictError):
            await use_cases.export_report(
                uow,
                storage=storage,  # type: ignore[arg-type]
                organization_id=organization_id,
                user_id=uuid.UUID(user_id),
                report_id=generating.id,
            )

    async def test_a_cross_organization_export_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        other = OrganizationId(new_id())
        report, _, storage = await seed_report(uow, organization_id=organization_id)
        other_user = await seed_member(uow, organization_id=other)

        with pytest.raises(NotFoundError):
            await use_cases.export_report(
                uow,
                storage=storage,  # type: ignore[arg-type]
                organization_id=other,
                user_id=other_user,
                report_id=report.id,
            )

    async def test_a_read_only_member_cannot_export(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(
            uow, organization_id=organization_id, role=MembershipRole.VIEWER
        )

        with pytest.raises(PermissionDeniedError):
            await use_cases.export_report(
                uow,
                storage=storage,  # type: ignore[arg-type]
                organization_id=organization_id,
                user_id=uuid.UUID(user_id),
                report_id=report.id,
            )


class TestGetReportExport:
    async def test_the_export_is_resolved_for_a_member(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)
        await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        export = await use_cases.get_report_export(
            uow,
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )

        assert await use_cases.read_export_bytes(storage, export) != b""  # type: ignore[arg-type]

    async def test_a_report_without_an_export_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        report, user_id, _ = await seed_report(uow, organization_id=organization_id)

        with pytest.raises(NotFoundError):
            await use_cases.get_report_export(
                uow,
                organization_id=organization_id,
                user_id=uuid.UUID(user_id),
                report_id=report.id,
            )

    async def test_a_cross_organization_download_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        other = OrganizationId(new_id())
        report, user_id, storage = await seed_report(uow, organization_id=organization_id)
        await use_cases.export_report(
            uow,
            storage=storage,  # type: ignore[arg-type]
            organization_id=organization_id,
            user_id=uuid.UUID(user_id),
            report_id=report.id,
        )
        other_user = await seed_member(uow, organization_id=other)

        with pytest.raises(NotFoundError):
            await use_cases.get_report_export(
                uow,
                organization_id=other,
                user_id=other_user,
                report_id=report.id,
            )

    async def test_a_nonexistent_report_is_not_found(self) -> None:
        uow = UnitOfWorkStub()
        organization_id = OrganizationId(new_id())
        user_id = await seed_member(uow, organization_id=organization_id)

        with pytest.raises(NotFoundError):
            await use_cases.get_report_export(
                uow,
                organization_id=organization_id,
                user_id=user_id,
                report_id=ReportId(new_id()),
            )
