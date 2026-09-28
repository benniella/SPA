from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ml.detection.detector import Detector
from ml.detection.registry import UnknownDetectorError
from ml.detection.types import Track
from ml.pipelines.cv_pipeline import CvPipeline, CvPipelineConfig, CvRunResult
from ml.tracking.tracker import Tracker
from ml.video.types import VideoDecodeError

from app.application.ports.processing import (
    ProcessingContext,
    ProcessingOutcome,
    ProgressReporter,
)
from app.application.ports.unit_of_work import UnitOfWorkFactory
from app.application.ports.video_storage import VideoStorage
from app.core.config import Settings
from app.core.errors import ProcessingFailedError
from app.domain.shared import AnalysisRunId, OrganizationId, VideoId
from app.domain.tracking.entities import TrackedObservation, TrackingDataset

logger = logging.getLogger(__name__)

#: A decode failure or an unavailable detector is deterministic for a given
#: video and model, so retrying it only burns compute. Transient failures
#: (storage, database) are left to the worker's bounded retry budget.
_FATAL_CV_ERRORS = (VideoDecodeError, UnknownDetectorError)


@dataclass(slots=True)
class _RunTotals:
    frames_sampled: int = 0
    detections: int = 0
    tracks: int = 0
    track_ids: set[int] = field(default_factory=set)


class CvProcessingPipeline:

    def __init__(
        self,
        *,
        settings: Settings,
        storage: VideoStorage,
        uow_factory: UnitOfWorkFactory,
        detector: Detector | None = None,
        tracker: Tracker | None = None,
    ) -> None:
        self._settings = settings
        self._storage = storage
        self._uow_factory = uow_factory
        self._detector = detector
        self._tracker = tracker

    async def run(
        self, context: ProcessingContext, reporter: ProgressReporter
    ) -> ProcessingOutcome:
        await reporter.report(5.0)
        await self._verify_object(context)

        # Ingestion and analysis are separate jobs. A job with no run still does
        # the CV work; there is simply nothing to attribute the output to, so it
        # is not persisted as an analysis result.
        if context.analysis_run_id is None:
            logger.info(
                "processing ran without an analysis run",
                extra={"video_id": context.video_id},
            )
            await reporter.report(100.0)
            return ProcessingOutcome(progress_percent=100.0)

        run_id = await self._begin_run(context)
        try:
            totals = await self._execute(context, run_id, reporter)
        except _FATAL_CV_ERRORS as exc:
            message = _failure_message(exc)
            await self._fail_run(run_id, message)
            raise ProcessingFailedError(message) from exc
        except Exception as exc:
            await self._fail_run(run_id, _failure_message(exc))
            raise

        await self._complete_run(run_id, totals)
        await reporter.report(100.0)
        logger.info(
            "cv pipeline completed",
            extra={
                "video_id": context.video_id,
                "frames_sampled": totals.frames_sampled,
                "detections": totals.detections,
                "tracks": totals.tracks,
                "track_ids": len(totals.track_ids),
            },
        )
        return ProcessingOutcome(progress_percent=100.0)

    async def _verify_object(self, context: ProcessingContext) -> None:
        stored = await self._storage.stat(context.storage_key)
        if stored is None:
            raise ProcessingFailedError(
                "The stored object for this video could not be found.",
                details={"video_id": context.video_id},
            )
        if context.size_bytes is not None and stored.size_bytes != context.size_bytes:
            raise ProcessingFailedError(
                "The stored object no longer matches the recorded size.",
                details={"video_id": context.video_id},
            )

    async def _begin_run(self, context: ProcessingContext) -> AnalysisRunId:
        if context.analysis_run_id is None:  # pragma: no cover - guarded by the caller
            raise ProcessingFailedError(
                "This video has no analysis run to record results against.",
                details={"video_id": context.video_id},
            )
        uow = self._uow_factory()
        async with uow:
            run = await uow.analysis_runs.get(AnalysisRunId(_uuid(context.analysis_run_id)))
            if run is None or run.organization_id != OrganizationId(_uuid(context.organization_id)):
                raise ProcessingFailedError(
                    "The analysis run for this video does not exist.",
                    details={"video_id": context.video_id},
                )
            if not run.is_terminal:
                run.start()
                await uow.analysis_runs.update(run)
                await uow.commit()
            return run.id

    async def _execute(
        self,
        context: ProcessingContext,
        run_id: AnalysisRunId,
        reporter: ProgressReporter,
    ) -> _RunTotals:
        path = self._resolve_local_path(context)
        dataset = await self._create_dataset(run_id, context)
        pipeline = self._build_pipeline()
        totals = _RunTotals()
        pending: list[TrackedObservation] = []
        batch_size = self._settings.cv_track_batch_size

        loop = asyncio.get_running_loop()
        last_reported = 0.0
        pending_reports: set[asyncio.Task[None]] = set()

        def on_tracks(tracks: list[Track]) -> None:
            pending.extend(_to_observations(tracks))
            totals.tracks += len(tracks)
            totals.track_ids.update(track.track_id for track in tracks)
            if len(pending) >= batch_size:
                # Decoding and inference run in a worker thread, so a batch is
                # flushed by scheduling the write onto the event loop and
                # waiting for it: memory stays bounded to one batch, not one
                # video.
                asyncio.run_coroutine_threadsafe(
                    self._persist_pending(dataset, list(pending)), loop
                ).result()
                pending.clear()

        def on_progress(processed: int, total: int) -> None:
            nonlocal last_reported
            percent = 5.0 + 90.0 * (processed / total) if total else 5.0
            if percent <= last_reported:
                return
            last_reported = percent
            task = loop.create_task(reporter.report(percent))
            pending_reports.add(task)
            task.add_done_callback(pending_reports.discard)

        try:
            result = await asyncio.to_thread(
                pipeline.run,
                str(path),
                on_tracks=on_tracks,
                on_progress=on_progress,
            )
        finally:
            # A partial run still persists what it produced, and the batch list
            # is cleared either way so no frame data outlives the run.
            await self._persist_pending(dataset, pending)
            pending.clear()
            if pending_reports:
                await asyncio.gather(*pending_reports, return_exceptions=True)

        totals.frames_sampled = result.frames_sampled
        totals.detections = result.detections
        await self._finalize_dataset(dataset, result)
        return totals

    def _build_pipeline(self) -> CvPipeline:
        config = CvPipelineConfig(
            detector_name=self._settings.cv_detector,
            confidence_threshold=self._settings.cv_confidence_threshold,
            device=self._settings.cv_device,
            model_path=self._settings.cv_detector_model_path,
            frame_interval=self._settings.cv_frame_interval,
            min_box_height=self._settings.cv_min_box_height,
        )
        return CvPipeline(config, detector=self._detector, tracker=self._tracker)

    async def _create_dataset(
        self, run_id: AnalysisRunId, context: ProcessingContext
    ) -> TrackingDataset:
        dataset = TrackingDataset(
            organization_id=OrganizationId(_uuid(context.organization_id)),
            video_id=VideoId(_uuid(context.video_id)),
            analysis_run_id=run_id,
            provenance={
                "detector": self._settings.cv_detector,
                "frame_interval": self._settings.cv_frame_interval,
                "confidence_threshold": self._settings.cv_confidence_threshold,
            },
        )
        uow = self._uow_factory()
        async with uow:
            await uow.tracking_datasets.add(dataset)
            await uow.commit()
        return dataset

    async def _persist_pending(
        self, dataset: TrackingDataset, pending: list[TrackedObservation]
    ) -> None:
        if not pending:
            return
        uow = self._uow_factory()
        async with uow:
            await uow.track_observations.add_batch(dataset, list(pending))
            await uow.commit()

    async def _finalize_dataset(self, dataset: TrackingDataset, result: CvRunResult) -> None:
        metadata = result.metadata
        uow = self._uow_factory()
        async with uow:
            stored = await uow.tracking_datasets.get(dataset.id)
            if stored is None:
                return
            stored.frame_rate = metadata.fps if metadata is not None else None
            stored.frame_count = metadata.frame_count if metadata is not None else None
            stored.object_count = len(result.track_ids)
            await uow.tracking_datasets.update(stored)
            await uow.commit()

    async def _complete_run(self, run_id: AnalysisRunId, totals: _RunTotals) -> None:
        uow = self._uow_factory()
        async with uow:
            run = await uow.analysis_runs.get(run_id)
            if run is None or run.is_terminal:
                return
            run.stage_results["detection"] = {
                "model": self._settings.cv_detector,
                "frames_sampled": totals.frames_sampled,
                "detections": totals.detections,
            }
            run.stage_results["tracking"] = {
                "tracks": totals.tracks,
                "track_ids": len(totals.track_ids),
            }
            run.succeed()
            await uow.analysis_runs.update(run)
            await uow.commit()

    async def _fail_run(self, run_id: AnalysisRunId, message: str) -> None:
        uow = self._uow_factory()
        async with uow:
            run = await uow.analysis_runs.get(run_id)
            if run is None or run.is_terminal:
                return
            run.fail(message)
            await uow.analysis_runs.update(run)
            await uow.commit()

    def _resolve_local_path(self, context: ProcessingContext) -> Path:
        opener = getattr(self._storage, "path_for", None)
        if opener is None:
            raise ProcessingFailedError(
                "The configured storage backend cannot expose a local video path."
            )
        return Path(opener(context.storage_key))


def _to_observations(tracks: list[Track]) -> list[TrackedObservation]:
    return [
        TrackedObservation(
            track_id=track.track_id,
            class_id=track.class_id,
            confidence=track.confidence,
            x1=track.box.x1,
            y1=track.box.y1,
            x2=track.box.x2,
            y2=track.box.y2,
            frame_index=track.frame_index,
            timestamp_seconds=track.timestamp_seconds,
        )
        for track in tracks
    ]


def _failure_message(exc: Exception) -> str:
    if isinstance(exc, VideoDecodeError):
        return "The video could not be decoded."
    if isinstance(exc, UnknownDetectorError):
        return "The configured detector is not available."
    text = str(exc).strip()
    return text or "Processing failed."


def _uuid(value: str) -> uuid.UUID:
    return uuid.UUID(value)
