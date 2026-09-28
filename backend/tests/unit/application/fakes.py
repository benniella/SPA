"""In-memory fakes for the application-layer ports.

Fakes rather than mocks: a fake implements the port's behaviour (an object goes
in, the same object comes out) so tests assert on outcomes instead of on
interaction choreography. They also make a test that would need a database run in
microseconds.
"""

from __future__ import annotations

import uuid
from datetime import date

from app.domain.analysis.entities import AnalysisRun, AnalysisRunStatus
from app.domain.analysis.metrics import PerformanceMetric
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.matches.entities import Match
from app.domain.metrics.types import TrackMetricRecord
from app.domain.organizations.entities import Organization, OrganizationMembership
from app.domain.players.entities import Player
from app.domain.reports.entities import Report
from app.domain.shared import (
    AnalysisRunId,
    JobId,
    MatchId,
    OrganizationId,
    PlayerId,
    ReportId,
    TeamId,
    TrackObservationId,
    UserId,
    VideoId,
    utcnow,
)
from app.domain.teams.entities import Team
from app.domain.tracking.entities import TrackedObservation, TrackingDataset, TrackRecord
from app.domain.users.entities import User
from app.domain.videos.entities import Video


def _key(value: object) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class _FakeRepository:
    """Common single-entity storage keyed by id."""

    def __init__(self) -> None:
        self._items: dict[uuid.UUID, object] = {}
        self.added: list[object] = []

    @property
    def items(self) -> list[object]:
        return list(self._items.values())

    async def add(self, entity: object) -> None:
        self._items[_key(entity.id)] = entity  # type: ignore[attr-defined]
        self.added.append(entity)

    async def get(self, entity_id: object) -> object | None:
        return self._items.get(_key(entity_id))

    async def delete(self, entity: object) -> None:
        self._items.pop(_key(entity.id), None)  # type: ignore[attr-defined]


class FakeOrganizationRepository(_FakeRepository):
    def __init__(self) -> None:
        super().__init__()
        self.memberships: list[OrganizationMembership] = []

    async def add(self, organization: Organization) -> None:
        await super().add(organization)

    async def get(self, organization_id: OrganizationId) -> Organization | None:
        return await super().get(organization_id)  # type: ignore[return-value]

    async def get_membership(
        self,
        organization_id: OrganizationId,
        user_id: UserId,
    ) -> OrganizationMembership | None:
        for membership in self.memberships:
            if membership.organization_id == organization_id and membership.user_id == user_id:
                return membership
        return None

    async def get_by_slug(self, slug: str) -> Organization | None:
        for item in self.items:
            if isinstance(item, Organization) and item.slug.value == slug:
                return item
        return None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Organization]:
        return [item for item in self.items if isinstance(item, Organization)][  # type: ignore[misc]
            offset : offset + limit
        ]


class FakeUserRepository(_FakeRepository):
    async def get_by_email(self, email: str) -> User | None:
        for item in self.items:
            if isinstance(item, User) and item.email.value == email.strip().lower():
                return item
        return None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[User]:
        return [item for item in self.items if isinstance(item, User)][offset : offset + limit]  # type: ignore[misc]


class FakeTeamRepository(_FakeRepository):
    async def get(self, team_id: TeamId) -> Team | None:
        return await super().get(team_id)  # type: ignore[return-value]

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Team]:
        matches = [
            item
            for item in self.items
            if isinstance(item, Team) and item.organization_id == organization_id
        ]
        return matches[offset : offset + limit]


class FakePlayerRepository(_FakeRepository):
    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]:
        matches = [
            item
            for item in self.items
            if isinstance(item, Player) and item.organization_id == organization_id
        ]
        return matches[offset : offset + limit]

    async def list_for_team(
        self,
        team_id: TeamId,
        *,
        on_date: date | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]:
        return self.items[offset : offset + limit]  # type: ignore[return-value]


class FakeMatchRepository(_FakeRepository):
    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Match]:
        matches = [
            item
            for item in self.items
            if isinstance(item, Match) and item.organization_id == organization_id
        ]
        return matches[offset : offset + limit]


class FakeVideoRepository(_FakeRepository):
    async def add(self, video: Video) -> None:
        await super().add(video)

    async def get(self, video_id: VideoId) -> Video | None:
        return await super().get(video_id)  # type: ignore[return-value]

    async def list_for_match(self, match_id: MatchId) -> list[Video]:
        return [
            item for item in self.items if isinstance(item, Video) and item.match_id == match_id
        ]

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Video]:
        matches = [
            item
            for item in self.items
            if isinstance(item, Video) and item.organization_id == organization_id
        ]
        return matches[offset : offset + limit]

    async def update(self, video: Video) -> None:
        self._items[_key(video.id)] = video

    async def delete(self, video: Video) -> None:
        self._items.pop(_key(video.id), None)


class FakeAnalysisRunRepository(_FakeRepository):
    async def add(self, run: AnalysisRun) -> None:
        await super().add(run)

    async def get(self, run_id: AnalysisRunId) -> AnalysisRun | None:
        return await super().get(run_id)  # type: ignore[return-value]

    async def list_for_video(self, video_id: VideoId) -> list[AnalysisRun]:
        return [
            item
            for item in self.items
            if isinstance(item, AnalysisRun) and item.video_id == video_id
        ]

    async def list_by_status(
        self,
        status: AnalysisRunStatus,
        *,
        limit: int = 50,
    ) -> list[AnalysisRun]:
        matches = [
            item for item in self.items if isinstance(item, AnalysisRun) and item.status == status
        ]
        return matches[:limit]

    async def update(self, run: AnalysisRun) -> None:
        self._items[_key(run.id)] = run


class FakeProcessingJobRepository(_FakeRepository):
    async def add(self, job: ProcessingJob) -> None:
        await super().add(job)

    async def get(self, job_id: JobId) -> ProcessingJob | None:
        return await super().get(job_id)  # type: ignore[return-value]

    async def list_for_video(self, video_id: VideoId, *, limit: int = 50) -> list[ProcessingJob]:
        matches = [
            item
            for item in self.items
            if isinstance(item, ProcessingJob) and item.video_id == video_id
        ]
        return matches[:limit]

    async def find_active(self, video_id: VideoId, job_type: str) -> ProcessingJob | None:
        for item in reversed(self.items):
            if (
                isinstance(item, ProcessingJob)
                and item.video_id == video_id
                and item.job_type == job_type
                and item.status.value in {JobStatus.QUEUED, JobStatus.RUNNING}
            ):
                return item
        return None

    async def update(self, job: ProcessingJob) -> None:
        self._items[_key(job.id)] = job


class FakeTrackingDatasetRepository(_FakeRepository):
    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackingDataset]:
        return [
            item
            for item in self.items
            if isinstance(item, TrackingDataset) and item.analysis_run_id == run_id
        ]

    async def update(self, dataset: TrackingDataset) -> None:
        self._items[_key(dataset.id)] = dataset


class FakeTrackObservationRepository:
    """In-memory per-frame observations, keyed by the run they belong to."""

    def __init__(self) -> None:
        self.by_run: dict[uuid.UUID, list[TrackRecord]] = {}
        self.batches: list[int] = []

    async def add_batch(
        self,
        dataset: TrackingDataset,
        observations: list[TrackedObservation],
    ) -> int:
        if not observations:
            return 0
        records = self.by_run.setdefault(_key(dataset.analysis_run_id), [])
        records.extend(
            TrackRecord(
                id=TrackObservationId(uuid.uuid4()),
                organization_id=dataset.organization_id,
                video_id=dataset.video_id,
                analysis_run_id=dataset.analysis_run_id,
                observation=observation,
                created_at=utcnow(),
            )
            for observation in observations
        )
        self.batches.append(len(observations))
        return len(observations)

    async def list_for_run(
        self,
        run_id: AnalysisRunId,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]:
        records = self.by_run.get(_key(run_id), [])
        return records[offset : offset + limit]

    async def count_for_run(self, run_id: AnalysisRunId) -> int:
        return len(self.by_run.get(_key(run_id), []))

    async def distinct_track_count(self, run_id: AnalysisRunId) -> int:
        return len({record.observation.track_id for record in self.by_run.get(_key(run_id), [])})

    async def list_for_track(
        self,
        run_id: AnalysisRunId,
        track_id: int,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]:
        records = [
            record
            for record in self.by_run.get(_key(run_id), [])
            if record.observation.track_id == track_id
        ]
        records.sort(key=lambda record: record.observation.frame_index)
        return records[offset : offset + limit]

    async def track_ids(self, run_id: AnalysisRunId) -> list[int]:
        return sorted({record.observation.track_id for record in self.by_run.get(_key(run_id), [])})

    async def coordinate_extent(
        self, run_id: AnalysisRunId
    ) -> tuple[float, float, float, float] | None:
        records = self.by_run.get(_key(run_id), [])
        if not records:
            return None
        return (
            min(record.observation.x1 for record in records),
            min(record.observation.y1 for record in records),
            max(record.observation.x2 for record in records),
            max(record.observation.y2 for record in records),
        )


class FakeTrackMetricRepository:
    """In-memory derived metrics, keyed by the run they belong to.

    'replace_for_run' mirrors the SQL implementation: a run's metrics are replaced
    wholesale, which is what makes a retried calculation idempotent.
    """

    def __init__(self) -> None:
        self.by_run: dict[uuid.UUID, list[TrackMetricRecord]] = {}

    async def replace_for_run(
        self,
        run_id: AnalysisRunId,
        metrics: list[TrackMetricRecord],
    ) -> None:
        self.by_run[_key(run_id)] = list(metrics)

    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackMetricRecord]:
        return list(self.by_run.get(_key(run_id), []))

    async def count_for_run(self, run_id: AnalysisRunId) -> int:
        return len(self.by_run.get(_key(run_id), []))


class FakePerformanceMetricRepository:
    def __init__(self) -> None:
        self.added: list[PerformanceMetric] = []

    async def add_many(self, metrics: list[PerformanceMetric]) -> None:
        self.added.extend(metrics)

    async def list_for_run(self, run_id: AnalysisRunId) -> list[PerformanceMetric]:
        return [metric for metric in self.added if metric.analysis_run_id == run_id]

    async def list_for_player(
        self,
        player_id: PlayerId,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PerformanceMetric]:
        matches = [metric for metric in self.added if metric.player_id == player_id]
        return matches[offset : offset + limit]


class FakeReportRepository(_FakeRepository):
    async def get(self, report_id: ReportId) -> Report | None:
        return await super().get(report_id)  # type: ignore[return-value]

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Report]:
        matches = [
            item
            for item in self.items
            if isinstance(item, Report) and item.organization_id == organization_id
        ]
        return matches[offset : offset + limit]


class UnitOfWorkStub:
    """A unit of work backed entirely by in-memory repositories."""

    def __init__(self) -> None:
        self.organizations = FakeOrganizationRepository()
        self.users = FakeUserRepository()
        self.teams = FakeTeamRepository()
        self.players = FakePlayerRepository()
        self.matches = FakeMatchRepository()
        self.videos = FakeVideoRepository()
        self.analysis_runs = FakeAnalysisRunRepository()
        self.processing_jobs = FakeProcessingJobRepository()
        self.tracking_datasets = FakeTrackingDatasetRepository()
        self.track_observations = FakeTrackObservationRepository()
        self.track_metrics = FakeTrackMetricRepository()
        self.metrics = FakePerformanceMetricRepository()
        self.reports = FakeReportRepository()
        self.commits = 0
        self.rollbacks = 0

    async def __aenter__(self) -> UnitOfWorkStub:
        return self

    async def __aexit__(self, exc_type: object, exc: object, tb: object) -> None:
        return None

    async def commit(self) -> None:
        self.commits += 1

    async def rollback(self) -> None:
        self.rollbacks += 1
