"""Job dispatcher port.

Route handlers create an analysis run and hand a small, JSON-serialisable
payload to a dispatcher; they never open a video or block on computer vision.
Because this is a port, moving from inline execution to a worker pool is an
adapter and configuration change, not a change to any use case or route.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


class JobKind:
    """The kinds of asynchronous work SPA dispatches."""

    __slots__ = ("value",)

    INGEST_VIDEO = "ingest_video"
    RUN_ANALYSIS = "run_analysis"
    GENERATE_REPORT = "generate_report"

    ALLOWED = frozenset({INGEST_VIDEO, RUN_ANALYSIS, GENERATE_REPORT})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown job kind: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __repr__(self) -> str:
        return f"JobKind({self.value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JobKind):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


@dataclass(frozen=True, slots=True)
class Job:
    """A unit of asynchronous work, ready to be serialised.

    'payload' carries identifiers only — never blobs, never ORM objects — so it
    survives JSON serialisation into a broker. 'idempotency_key' lets a retried
    dispatch avoid starting duplicate work on an at-least-once queue.
    """

    kind: JobKind
    payload: dict[str, Any] = field(default_factory=dict)
    organization_id: str | None = None
    idempotency_key: str | None = None
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")


@dataclass(frozen=True, slots=True)
class JobResult:
    """What a dispatcher reports back to the caller.

    'accepted' means queued or executed, not succeeded; the worker writes the
    real outcome to the analysis run.
    """

    accepted: bool
    job_id: str | None = None
    detail: str | None = None


@runtime_checkable
class JobDispatcher(Protocol):
    """Dispatches jobs to whatever executes them."""

    async def dispatch(self, job: Job) -> JobResult: ...


@runtime_checkable
class JobRegistry(Protocol):
    """Maps a job kind to the handler that executes it, in the worker process."""

    def register(self, kind: JobKind, handler: JobHandler) -> None: ...

    def resolve(self, kind: JobKind) -> JobHandler | None: ...


@runtime_checkable
class JobHandler(Protocol):
    """Executes one job kind, inside the worker process."""

    async def __call__(self, payload: dict[str, Any]) -> None: ...
