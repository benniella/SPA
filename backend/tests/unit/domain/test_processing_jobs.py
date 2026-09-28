"""Processing job lifecycle tests.

The invariants that matter: a job never reports completion without having run, a
retry budget is shared across redeliveries rather than reset, and progress cannot
be reported on a finished job.
"""

from __future__ import annotations

import pytest

from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.shared import OrganizationId, VideoId, new_id


def make_job(*, max_attempts: int = 3) -> ProcessingJob:
    return ProcessingJob(
        organization_id=OrganizationId(new_id()),
        video_id=VideoId(new_id()),
        job_type="ingest_video",
        max_attempts=max_attempts,
    )


class TestJobLifecycle:
    def test_starts_queued_with_no_attempts(self) -> None:
        job = make_job()
        assert job.status == JobStatus.QUEUED
        assert job.attempt == 0
        assert job.started_at is None
        assert job.completed_at is None

    def test_start_moves_to_running_and_counts_the_attempt(self) -> None:
        job = make_job()
        job.start()
        assert job.status == JobStatus.RUNNING
        assert job.attempt == 1
        assert job.started_at is not None

    def test_starting_a_running_job_is_idempotent(self) -> None:
        job = make_job()
        job.start()
        job.start()
        # A redelivered message must not consume a second attempt.
        assert job.attempt == 1

    def test_complete_clears_the_error_and_finishes(self) -> None:
        job = make_job()
        job.start()
        job.fail("transient")
        job.requeue()
        job.start()
        job.complete()
        assert job.status == JobStatus.COMPLETED
        assert job.progress == 100.0
        assert job.error is None
        assert job.completed_at is not None

    def test_cannot_start_a_completed_job(self) -> None:
        job = make_job()
        job.start()
        job.complete()
        with pytest.raises(ValueError):
            job.start()

    def test_cannot_report_progress_on_a_finished_job(self) -> None:
        job = make_job()
        job.start()
        job.complete()
        with pytest.raises(ValueError):
            job.report_progress(50.0)

    def test_progress_is_bounded(self) -> None:
        job = make_job()
        job.start()
        with pytest.raises(ValueError):
            job.report_progress(101.0)


class TestRetryBudget:
    def test_requeue_preserves_the_attempt_count(self) -> None:
        job = make_job(max_attempts=3)
        job.start()
        job.fail("boom")
        job.requeue()
        assert job.status == JobStatus.QUEUED
        assert job.attempt == 1

    def test_cannot_requeue_beyond_the_budget(self) -> None:
        job = make_job(max_attempts=1)
        job.start()
        job.fail("boom")
        assert job.can_retry is False
        with pytest.raises(ValueError):
            job.requeue()

    def test_cannot_requeue_a_running_job(self) -> None:
        job = make_job()
        job.start()
        with pytest.raises(ValueError):
            job.requeue()
