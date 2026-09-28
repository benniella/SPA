from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ProcessingContext:
    job_id: str
    organization_id: str
    video_id: str
    storage_key: str
    content_type: str | None
    size_bytes: int | None
    #: The analysis run this job produces results for. Optional because an
    #: ingestion job has no run yet; a run-producing pipeline requires it.
    analysis_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ProcessingOutcome:
    progress_percent: float = 100.0


@runtime_checkable
class ProgressReporter(Protocol):
    async def report(self, percent: float) -> None: ...


@runtime_checkable
class ProcessingPipeline(Protocol):
    async def run(
        self, context: ProcessingContext, reporter: ProgressReporter
    ) -> ProcessingOutcome: ...
