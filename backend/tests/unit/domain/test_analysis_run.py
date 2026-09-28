"""Analysis-run lifecycle tests.

The state machine is the contract between the synchronous API and the
asynchronous worker, so it is tested at the domain level where it lives.
"""

from __future__ import annotations

import pytest

from app.domain.analysis.entities import (
    AnalysisPipelineSpec,
    AnalysisRun,
    AnalysisRunStatus,
    default_pipeline,
)
from app.domain.shared import OrganizationId, VideoId, new_id


def _run() -> AnalysisRun:
    return AnalysisRun(
        organization_id=OrganizationId(new_id()),
        video_id=VideoId(new_id()),
        pipeline=default_pipeline(),
    )


class TestPipelineSpec:
    def test_rejects_duplicate_stages(self) -> None:
        with pytest.raises(ValueError):
            AnalysisPipelineSpec(stages=("tracking", "tracking"))

    def test_default_pipeline_stages(self) -> None:
        assert default_pipeline().stages == (
            "ingest",
            "detection",
            "tracking",
            "movement",
            "metrics",
        )


class TestAnalysisRun:
    def test_requires_at_least_one_stage(self) -> None:
        with pytest.raises(ValueError):
            AnalysisRun(
                organization_id=OrganizationId(new_id()),
                video_id=VideoId(new_id()),
                pipeline=AnalysisPipelineSpec(stages=()),
            )

    def test_starts_pending(self) -> None:
        run = _run()
        assert run.status == AnalysisRunStatus.PENDING
        assert run.progress_percent == 0.0
        assert not run.is_terminal

    def test_happy_path(self) -> None:
        run = _run()
        run.queue()
        run.start()
        run.report_progress(40.0, stage="detection")
        run.succeed()

        assert run.status == AnalysisRunStatus.SUCCEEDED
        assert run.progress_percent == 100.0
        assert run.is_terminal
        assert run.duration_seconds is not None
        assert run.stage_results["detection"] == {"completed": True}

    def test_partial_success_is_distinct_from_success(self) -> None:
        run = _run()
        run.start()
        run.succeed(partial=True)
        # Tracking data can be usable even when a later metrics stage failed;
        # collapsing this into 'failed' would discard expensive valid work.
        assert run.status == AnalysisRunStatus.PARTIALLY_SUCCEEDED
        assert run.is_terminal

    def test_cannot_queue_twice(self) -> None:
        run = _run()
        run.queue()
        with pytest.raises(ValueError):
            run.queue()

    def test_cannot_start_a_finished_run(self) -> None:
        run = _run()
        run.start()
        run.succeed()
        with pytest.raises(ValueError):
            run.start()

    def test_failure_records_a_message(self) -> None:
        run = _run()
        run.start()
        run.fail("object storage unavailable")
        assert run.status == AnalysisRunStatus.FAILED
        assert run.error_message == "object storage unavailable"
        assert run.finished_at is not None

    def test_progress_is_bounded(self) -> None:
        run = _run()
        run.start()
        with pytest.raises(ValueError):
            run.report_progress(120.0)

    def test_cannot_cancel_a_finished_run(self) -> None:
        run = _run()
        run.start()
        run.succeed()
        with pytest.raises(ValueError):
            run.cancel()


class TestAnalysisRunStatus:
    def test_terminal_states(self) -> None:
        for value in ("succeeded", "partially_succeeded", "failed", "cancelled"):
            assert AnalysisRunStatus(value).is_terminal

    def test_in_flight_states_are_not_terminal(self) -> None:
        for value in ("pending", "queued", "running"):
            assert not AnalysisRunStatus(value).is_terminal

    def test_rejects_unknown_status(self) -> None:
        with pytest.raises(ValueError):
            AnalysisRunStatus("exploded")
