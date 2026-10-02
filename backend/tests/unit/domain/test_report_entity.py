from __future__ import annotations

import pytest

from app.domain.reports.entities import Report, ReportScope, ReportStatus
from app.domain.shared import AnalysisRunId, OrganizationId, new_id


def report(**overrides: object) -> Report:
    run_id = AnalysisRunId(new_id())
    defaults: dict[str, object] = {
        "organization_id": OrganizationId(new_id()),
        "title": "Analysis report",
        "scope": ReportScope(analysis_run_ids=(run_id,)),
    }
    defaults.update(overrides)
    return Report(**defaults)  # type: ignore[arg-type]


class TestReportLifecycle:
    def test_a_new_report_is_a_draft_with_a_definition_version(self) -> None:
        record = report()

        assert record.status == ReportStatus.DRAFT
        assert record.definition_version == "v1"
        assert record.generated_at is None

    def test_a_draft_can_start_generating(self) -> None:
        record = report()

        record.mark_generating()

        assert record.status == ReportStatus.GENERATING

    def test_a_generating_report_becomes_a_ready_snapshot(self) -> None:
        record = report()
        record.mark_generating()

        record.mark_ready()

        assert record.status == ReportStatus.READY
        assert record.generated_at is not None
        assert record.is_ready_snapshot() is True

    def test_a_ready_report_cannot_start_generating_again(self) -> None:
        record = report()
        record.mark_generating()
        record.mark_ready()

        with pytest.raises(ValueError):
            record.mark_generating()

    def test_a_failed_report_can_be_retried(self) -> None:
        record = report()
        record.mark_generating()
        record.mark_failed("composition failed")

        record.mark_generating()

        assert record.status == ReportStatus.GENERATING

    def test_an_empty_failure_message_is_rejected(self) -> None:
        record = report()
        record.mark_generating()

        with pytest.raises(ValueError):
            record.mark_failed("  ")

    def test_a_generating_report_is_not_a_ready_snapshot(self) -> None:
        record = report()
        record.mark_generating()

        assert record.is_ready_snapshot() is False

    def test_a_report_exposes_its_analysis_run(self) -> None:
        run_id = AnalysisRunId(new_id())

        record = report(scope=ReportScope(analysis_run_ids=(run_id,)))

        assert record.analysis_run_id == run_id


class TestReportScope:
    def test_a_scope_with_no_subject_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            ReportScope()

    def test_a_multi_run_scope_has_no_single_run(self) -> None:
        scope = ReportScope(analysis_run_ids=(AnalysisRunId(new_id()), AnalysisRunId(new_id())))

        assert scope.analysis_run_id is None

    def test_an_empty_title_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            report(title="   ")

    def test_an_empty_definition_version_is_rejected(self) -> None:
        with pytest.raises(ValueError):
            report(definition_version="")
