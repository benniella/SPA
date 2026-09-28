from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable

from app.application.ports.job_queue import JobQueue
from app.application.ports.processing import ProcessingContext, ProcessingPipeline
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.use_cases.metrics import METRICS_JOB_TYPE
from app.core.errors import AppError
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.shared import JobId, VideoId

logger = logging.getLogger(__name__)


class _ProgressReporter:
    """Writes progress to the job row as the pipeline reports it."""

    def __init__(self, uow_factory: UnitOfWorkFactory, job_id: JobId) -> None:
        self._uow_factory = uow_factory
        self._job_id = job_id
        self._last_reported = -1.0

    async def report(self, percent: float) -> None:
        if percent <= self._last_reported:
            return
        self._last_reported = percent
        uow = self._uow_factory()
        async with uow:
            job = await uow.processing_jobs.get(self._job_id)
            if job is None or job.is_terminal:
                return
            job.report_progress(percent)
            await uow.processing_jobs.update(job)
            await uow.commit()


class JobWorker:
    """Pulls jobs from the queue and runs them."""

    def __init__(
        self,
        *,
        uow_factory: UnitOfWorkFactory,
        queue: JobQueue,
        pipeline: ProcessingPipeline,
        metrics_pipeline: ProcessingPipeline | None = None,
        on_event: Callable[[ProcessingJob], object] | None = None,
    ) -> None:
        self._uow_factory = uow_factory
        self._queue = queue
        self._pipeline = pipeline
        # Metric calculation is a second stage over the same tracking data, not a
        # different job system: it implements the same port and runs here.
        self._metrics_pipeline = metrics_pipeline
        self._on_event = on_event

    def _pipeline_for(self, job: ProcessingJob) -> ProcessingPipeline:
        if job.job_type == METRICS_JOB_TYPE and self._metrics_pipeline is not None:
            return self._metrics_pipeline
        return self._pipeline

    async def run_once(self, *, timeout_seconds: int = 5) -> bool:
        """Claim and process one job. Returns whether a job was handled."""
        job_id = await self._queue.dequeue(timeout_seconds=timeout_seconds)
        if job_id is None:
            return False

        await self.process(JobId(_coerce_uuid(job_id)))
        return True

    async def serve(self, *, concurrency: int = 2, stop: asyncio.Event | None = None) -> None:
        """Run workers until 'stop' is set."""
        stop = stop or asyncio.Event()
        tasks = [asyncio.create_task(self._loop(stop)) for _ in range(max(1, concurrency))]
        try:
            await stop.wait()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            try:
                handled = await self.run_once()
            except Exception:
                logger.exception("worker loop iteration failed")
                await asyncio.sleep(1)
                continue
            if not handled:
                await asyncio.sleep(0)

    async def process(self, job_id: JobId) -> ProcessingJob | None:
        """Execute one job by identifier."""
        uow = self._uow_factory()
        async with uow:
            job = await uow.processing_jobs.get(job_id)
            if job is None:
                # A queued identifier with no row is a lost message, not work.
                logger.warning("job not found", extra={"job_id": str(job_id)})
                await self._queue.acknowledge(str(job_id))
                return None
            if job.status.value == JobStatus.COMPLETED:
                await self._queue.acknowledge(str(job_id))
                return job
            if job.status.value == JobStatus.RUNNING:
                # A redelivery while the job is running: leave it to the worker
                # already executing it rather than starting a second attempt.
                return job
            if job.status.value == JobStatus.FAILED and not job.can_retry:
                # A terminal failure that a stale delivery rediscovered. Starting
                # it would consume an attempt the budget never granted.
                await self._queue.acknowledge(str(job_id))
                return job

            video = await uow.videos.get(VideoId(job.video_id))
            if video is None or video.organization_id != job.organization_id:
                job.fail("The video no longer exists in this organization.")
                await uow.processing_jobs.update(job)
                await uow.commit()
                await self._queue.acknowledge(str(job_id))
                self._emit(job)
                return job

            analysis_run_id = await self._latest_run_id(uow, job)

            context = ProcessingContext(
                job_id=str(job.id),
                organization_id=str(job.organization_id),
                video_id=str(job.video_id),
                storage_key=video.storage_key,
                content_type=video.content_type,
                size_bytes=video.size_bytes,
                analysis_run_id=analysis_run_id,
            )

            job.start()
            try:
                video.mark_processing()
            except ValueError as exc:
                job.fail(str(exc))
                await uow.processing_jobs.update(job)
                await uow.commit()
                await self._queue.acknowledge(str(job_id))
                self._emit(job)
                return job
            await uow.processing_jobs.update(job)
            await uow.videos.update(video)
            await uow.commit()

        self._emit(job)
        logger.info("job started", extra={"job_id": str(job.id), "job_type": job.job_type})

        reporter = _ProgressReporter(self._uow_factory, job.id)
        try:
            await self._pipeline_for(job).run(context, reporter)
        except Exception as exc:
            await self._record_failure(job_id, exc)
            return None

        return await self._record_success(job_id)

    async def _record_success(self, job_id: JobId) -> ProcessingJob | None:
        uow = self._uow_factory()
        async with uow:
            job = await uow.processing_jobs.get(job_id)
            if job is None or job.is_terminal:
                return job
            video = await uow.videos.get(VideoId(job.video_id))
            if video is not None and video.organization_id == job.organization_id:
                video.mark_ready()
                await uow.videos.update(video)
            job.complete()
            await uow.processing_jobs.update(job)
            await uow.commit()

        await self._queue.acknowledge(str(job_id))
        self._emit(job)
        logger.info("job completed", extra={"job_id": str(job.id), "job_type": job.job_type})
        return job

    async def _record_failure(self, job_id: JobId, exc: Exception) -> ProcessingJob | None:
        # Only the message travels onward; a raw exception must not reach a client
        # or a log line unredacted.
        reason = exc.message if isinstance(exc, AppError) else "Processing failed."

        uow = self._uow_factory()
        async with uow:
            job = await uow.processing_jobs.get(job_id)
            if job is None:
                return None

            job.fail(reason)
            if job.can_retry:
                job.requeue()
                retry = True
            else:
                retry = False
                video = await uow.videos.get(VideoId(job.video_id))
                if video is not None and video.organization_id == job.organization_id:
                    video.mark_failed(reason)
                    await uow.videos.update(video)
            await uow.processing_jobs.update(job)
            await uow.commit()

        logger.warning(
            "job failed",
            extra={
                "job_id": str(job.id),
                "job_type": job.job_type,
                "attempt": job.attempt,
                "retrying": retry,
            },
        )

        if retry:
            await self._queue.requeue(str(job_id))
        else:
            await self._queue.acknowledge(str(job_id))
        self._emit(job)
        return job

    def _emit(self, job: ProcessingJob) -> None:
        if self._on_event is not None:
            self._on_event(job)

    async def _latest_run_id(self, uow: object, job: ProcessingJob) -> str | None:
        """The newest analysis run for this job's video, if any.

        Processing and analysis-run creation are separate API calls, so the run
        is resolved at execution time rather than carried on the job row. A job
        with no run is still valid work; the pipeline simply has nothing to
        attribute results to.
        """
        runs = await uow.analysis_runs.list_for_video(job.video_id)  # type: ignore[attr-defined]
        if not runs:
            return None
        return str(runs[0].id)


def _coerce_uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
