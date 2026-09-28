"""Worker execution tests.

The assertions that matter: a job that runs to completion marks the video ready,
a failure is retried only while the budget allows and then marks the video
failed, and a redelivered message never processes the same work twice.
"""

from __future__ import annotations

from app.application.ports.processing import (
    ProcessingContext,
    ProcessingOutcome,
    ProgressReporter,
)
from app.core.errors import ProcessingFailedError
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.shared import OrganizationId, VideoId, new_id
from app.domain.videos.entities import Video, VideoStatus
from app.infrastructure.jobs.queue import InMemoryJobQueue
from app.worker.runner import JobWorker
from tests.unit.application.fakes import UnitOfWorkStub


class RecordingPipeline:
    """A pipeline that records what it was asked to process."""

    def __init__(self, *, fail: bool = False) -> None:
        self.calls: list[ProcessingContext] = []
        self._fail = fail

    async def run(
        self, context: ProcessingContext, reporter: ProgressReporter
    ) -> ProcessingOutcome:
        self.calls.append(context)
        await reporter.report(50.0)
        if self._fail:
            raise ProcessingFailedError("The pipeline could not process this video.")
        await reporter.report(100.0)
        return ProcessingOutcome()


async def seed(uow: UnitOfWorkStub, *, max_attempts: int = 3) -> tuple[ProcessingJob, Video]:
    organization_id = OrganizationId(new_id())
    video = Video(
        organization_id=organization_id,
        original_filename="match.mp4",
        storage_key=f"{organization_id}/videos/match.mp4",
    )
    video.mark_uploaded(size_bytes=4096, content_type="video/mp4")
    await uow.videos.add(video)

    job = ProcessingJob(
        organization_id=organization_id,
        video_id=video.id,
        job_type="ingest_video",
        max_attempts=max_attempts,
    )
    await uow.processing_jobs.add(job)
    return job, video


def make_worker(uow: UnitOfWorkStub, pipeline: RecordingPipeline) -> JobWorker:
    return JobWorker(
        uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
        queue=InMemoryJobQueue(),
        pipeline=pipeline,
    )


class TestSuccessfulExecution:
    async def test_completes_the_job_and_marks_the_video_ready(self) -> None:
        uow = UnitOfWorkStub()
        job, video = await seed(uow)
        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        result = await worker.process(job.id)

        assert result is not None
        assert result.status == JobStatus.COMPLETED
        assert result.progress == 100.0
        assert video.status == VideoStatus.READY

    async def test_passes_only_server_derived_context_to_the_pipeline(self) -> None:
        uow = UnitOfWorkStub()
        job, video = await seed(uow)
        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)

        context = pipeline.calls[0]
        assert context.video_id == str(video.id)
        assert context.storage_key == video.storage_key
        assert context.organization_id == str(job.organization_id)

    async def test_passes_the_latest_analysis_run_to_the_pipeline(self) -> None:
        from app.domain.analysis.entities import AnalysisRun, default_pipeline

        uow = UnitOfWorkStub()
        job, video = await seed(uow)
        run = AnalysisRun(
            organization_id=job.organization_id,
            video_id=video.id,
            pipeline=default_pipeline(),
        )
        run.queue()
        await uow.analysis_runs.add(run)

        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)
        await worker.process(job.id)

        assert pipeline.calls[0].analysis_run_id == str(run.id)

    async def test_a_job_without_an_analysis_run_still_runs(self) -> None:
        uow = UnitOfWorkStub()
        job, _ = await seed(uow)
        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)

        assert pipeline.calls[0].analysis_run_id is None


class TestIdempotency:
    async def test_a_redelivered_completed_job_is_not_processed_again(self) -> None:
        uow = UnitOfWorkStub()
        job, _ = await seed(uow)
        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)
        await worker.process(job.id)

        assert len(pipeline.calls) == 1

    async def test_an_already_running_job_is_left_to_the_worker_executing_it(self) -> None:
        uow = UnitOfWorkStub()
        job, _ = await seed(uow)
        job.start()
        await uow.processing_jobs.update(job)

        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)
        assert pipeline.calls == []


class TestFailureAndRetry:
    async def test_a_failure_is_retried_while_the_budget_allows(self) -> None:
        uow = UnitOfWorkStub()
        job, video = await seed(uow)
        pipeline = RecordingPipeline(fail=True)
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)

        stored = await uow.processing_jobs.get(job.id)
        assert stored is not None
        assert stored.status == JobStatus.QUEUED
        assert stored.attempt == 1
        assert stored.error == "The pipeline could not process this video."
        # A retryable failure must not fail the video.
        assert video.status == VideoStatus.PROCESSING

    async def test_retries_are_bounded_and_end_in_a_failed_job(self) -> None:
        uow = UnitOfWorkStub()
        job, video = await seed(uow, max_attempts=2)
        pipeline = RecordingPipeline(fail=True)
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)
        await worker.process(job.id)
        await worker.process(job.id)

        stored = await uow.processing_jobs.get(job.id)
        assert stored is not None
        assert stored.status == JobStatus.FAILED
        assert stored.attempt == 2
        assert video.status == VideoStatus.FAILED

    async def test_a_missing_video_fails_the_job_without_running_the_pipeline(self) -> None:
        uow = UnitOfWorkStub()
        job, _ = await seed(uow)
        await uow.videos.delete(await uow.videos.get(job.video_id))

        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        await worker.process(job.id)

        stored = await uow.processing_jobs.get(job.id)
        assert stored is not None
        assert stored.status == JobStatus.FAILED
        assert pipeline.calls == []


class TestUnknownJob:
    async def test_an_unknown_job_identifier_is_acknowledged_not_crashed(self) -> None:
        uow = UnitOfWorkStub()
        pipeline = RecordingPipeline()
        worker = make_worker(uow, pipeline)

        result = await worker.process(VideoId(new_id()))  # type: ignore[arg-type]

        assert result is None
        assert pipeline.calls == []


class TestRunOnce:
    async def test_run_once_dequeues_and_processes_a_job(self) -> None:
        uow = UnitOfWorkStub()
        job, _ = await seed(uow)
        queue = InMemoryJobQueue()
        await queue.enqueue(str(job.id))

        pipeline = RecordingPipeline()
        worker = JobWorker(
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            queue=queue,
            pipeline=pipeline,
        )

        handled = await worker.run_once()
        assert handled is True
        assert len(pipeline.calls) == 1

    async def test_run_once_reports_an_empty_queue(self) -> None:
        uow = UnitOfWorkStub()
        worker = JobWorker(
            uow_factory=lambda: uow,  # type: ignore[arg-type,return-value]
            queue=InMemoryJobQueue(),
            pipeline=RecordingPipeline(),
        )
        assert await worker.run_once() is False
