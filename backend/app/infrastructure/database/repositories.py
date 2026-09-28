"""SQLAlchemy repository implementations.

Each repository is a thin translation between a domain entity and a session; no
business rules live here. Every organization-scoped read filters by organization,
and entities are returned rather than ORM models.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.analysis.entities import AnalysisRun
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
    TrackingDatasetId,
    UserId,
    VideoId,
)
from app.domain.teams.entities import Team
from app.domain.tracking.entities import TrackedObservation, TrackingDataset, TrackRecord
from app.domain.users.entities import User
from app.domain.videos.entities import Video
from app.infrastructure.database import mappers
from app.infrastructure.database.models import (
    AnalysisRunModel,
    MatchModel,
    OrganizationMembershipModel,
    OrganizationModel,
    PerformanceMetricModel,
    PlayerModel,
    ProcessingJobModel,
    ReportModel,
    TeamMembershipModel,
    TeamModel,
    TrackingDatasetModel,
    TrackMetricModel,
    TrackObservationModel,
    UserModel,
    VideoModel,
)


def _coerce_uuid(value: object) -> uuid.UUID:
    """Accept both ' 'uuid.UUID' ' and its string form from callers.

    Handy because job payloads are JSON and therefore carry ids as strings.
    """
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


class SqlOrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, organization: Organization) -> None:
        self._session.add(mappers.organization_to_model(organization))
        await self._session.flush()

    async def get(self, organization_id: OrganizationId) -> Organization | None:
        model = await self._session.get(OrganizationModel, _coerce_uuid(organization_id))
        return mappers.organization_to_domain(model) if model else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return mappers.organization_to_domain(model) if model else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Organization]:
        result = await self._session.execute(
            select(OrganizationModel)
            .order_by(OrganizationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [mappers.organization_to_domain(model) for model in result.scalars()]

    async def delete(self, organization: Organization) -> None:
        await self._session.execute(
            delete(OrganizationModel).where(OrganizationModel.id == organization.id)
        )

    async def get_membership(
        self,
        organization_id: OrganizationId,
        user_id: UserId,
    ) -> OrganizationMembership | None:
        result = await self._session.execute(
            select(OrganizationMembershipModel).where(
                OrganizationMembershipModel.organization_id == _coerce_uuid(organization_id),
                OrganizationMembershipModel.user_id == _coerce_uuid(user_id),
            )
        )
        model = result.scalar_one_or_none()
        return mappers.membership_to_domain(model) if model else None


class SqlUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, user: User) -> None:
        self._session.add(mappers.user_to_model(user))
        await self._session.flush()

    async def get(self, user_id: UserId) -> User | None:
        model = await self._session.get(UserModel, _coerce_uuid(user_id))
        return mappers.user_to_domain(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email.strip().lower())
        )
        model = result.scalar_one_or_none()
        return mappers.user_to_domain(model) if model else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[User]:
        result = await self._session.execute(
            select(UserModel).order_by(UserModel.created_at.desc()).limit(limit).offset(offset)
        )
        return [mappers.user_to_domain(model) for model in result.scalars()]


class SqlTeamRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, team: Team) -> None:
        self._session.add(mappers.team_to_model(team))
        await self._session.flush()

    async def get(self, team_id: TeamId) -> Team | None:
        model = await self._session.get(TeamModel, _coerce_uuid(team_id))
        return mappers.team_to_domain(model) if model else None

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Team]:
        result = await self._session.execute(
            select(TeamModel)
            .where(TeamModel.organization_id == _coerce_uuid(organization_id))
            .order_by(TeamModel.name)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.team_to_domain(model) for model in result.scalars()]

    async def delete(self, team: Team) -> None:
        await self._session.execute(delete(TeamModel).where(TeamModel.id == team.id))


class SqlPlayerRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, player: Player) -> None:
        self._session.add(mappers.player_to_model(player))
        await self._session.flush()

    async def get(self, player_id: PlayerId) -> Player | None:
        model = await self._session.get(PlayerModel, _coerce_uuid(player_id))
        return mappers.player_to_domain(model) if model else None

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]:
        result = await self._session.execute(
            select(PlayerModel)
            .where(PlayerModel.organization_id == _coerce_uuid(organization_id))
            .order_by(PlayerModel.display_name)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.player_to_domain(model) for model in result.scalars()]

    async def list_for_team(
        self,
        team_id: TeamId,
        *,
        on_date: object | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]:
        """List a team's players, optionally as registered on ' 'on_date' '.

        The date filter is applied in SQL against the membership window rather
        than in Python, so the query stays cheap as squads and seasons
        accumulate.
        """
        statement = (
            select(PlayerModel)
            .join(TeamMembershipModel, TeamMembershipModel.player_id == PlayerModel.id)
            .where(TeamMembershipModel.team_id == _coerce_uuid(team_id))
        )
        if isinstance(on_date, date):
            statement = statement.where(
                TeamMembershipModel.joined_on <= on_date,
                (TeamMembershipModel.left_on.is_(None)) | (TeamMembershipModel.left_on >= on_date),
            )
        statement = statement.order_by(PlayerModel.display_name).limit(limit).offset(offset)

        result = await self._session.execute(statement)
        return [mappers.player_to_domain(model) for model in result.scalars()]


class SqlMatchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, match: Match) -> None:
        self._session.add(mappers.match_to_model(match))
        await self._session.flush()

    async def get(self, match_id: MatchId) -> Match | None:
        model = await self._session.get(MatchModel, _coerce_uuid(match_id))
        return mappers.match_to_domain(model) if model else None

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Match]:
        result = await self._session.execute(
            select(MatchModel)
            .where(MatchModel.organization_id == _coerce_uuid(organization_id))
            .order_by(MatchModel.played_on.desc())
            .limit(limit)
            .offset(offset)
        )
        return [mappers.match_to_domain(model) for model in result.scalars()]

    async def delete(self, match: Match) -> None:
        await self._session.execute(delete(MatchModel).where(MatchModel.id == match.id))


class SqlVideoRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, video: Video) -> None:
        self._session.add(mappers.video_to_model(video))
        await self._session.flush()

    async def get(self, video_id: VideoId) -> Video | None:
        model = await self._session.get(VideoModel, _coerce_uuid(video_id))
        return mappers.video_to_domain(model) if model else None

    async def list_for_match(self, match_id: MatchId) -> list[Video]:
        result = await self._session.execute(
            select(VideoModel)
            .where(VideoModel.match_id == _coerce_uuid(match_id))
            .order_by(VideoModel.created_at)
        )
        return [mappers.video_to_domain(model) for model in result.scalars()]

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Video]:
        result = await self._session.execute(
            select(VideoModel)
            .where(VideoModel.organization_id == _coerce_uuid(organization_id))
            .order_by(VideoModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [mappers.video_to_domain(model) for model in result.scalars()]

    async def update(self, video: Video) -> None:
        """Persist mutations made to a domain entity already in the database."""
        model = await self._session.get(VideoModel, _coerce_uuid(video.id))
        if model is None:
            raise LookupError(f"Video {video.id} is not persisted.")
        mappers.apply_video_to_model(video, model)
        await self._session.flush()

    async def count_for_organization(self, organization_id: OrganizationId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(VideoModel)
            .where(VideoModel.organization_id == _coerce_uuid(organization_id))
        )
        return int(result.scalar_one())

    async def delete(self, video: Video) -> None:
        await self._session.execute(
            delete(VideoModel).where(VideoModel.id == _coerce_uuid(video.id))
        )


class SqlAnalysisRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, run: AnalysisRun) -> None:
        self._session.add(mappers.analysis_run_to_model(run))
        await self._session.flush()

    async def get(self, run_id: AnalysisRunId) -> AnalysisRun | None:
        model = await self._session.get(AnalysisRunModel, _coerce_uuid(run_id))
        return mappers.analysis_run_to_domain(model) if model else None

    async def list_for_video(self, video_id: VideoId) -> list[AnalysisRun]:
        result = await self._session.execute(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.video_id == _coerce_uuid(video_id))
            .order_by(AnalysisRunModel.created_at.desc())
        )
        return [mappers.analysis_run_to_domain(model) for model in result.scalars()]

    async def list_by_status(self, status: object, *, limit: int = 50) -> list[AnalysisRun]:
        result = await self._session.execute(
            select(AnalysisRunModel)
            .where(AnalysisRunModel.status == str(status))
            .order_by(AnalysisRunModel.created_at)
            .limit(limit)
        )
        return [mappers.analysis_run_to_domain(model) for model in result.scalars()]

    async def update(self, run: AnalysisRun) -> None:
        model = await self._session.get(AnalysisRunModel, _coerce_uuid(run.id))
        if model is None:
            raise LookupError(f"Analysis run {run.id} is not persisted.")
        mappers.apply_analysis_run_to_model(run, model)
        await self._session.flush()


class SqlProcessingJobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, job: ProcessingJob) -> None:
        self._session.add(mappers.processing_job_to_model(job))
        await self._session.flush()

    async def get(self, job_id: JobId) -> ProcessingJob | None:
        model = await self._session.get(ProcessingJobModel, _coerce_uuid(job_id))
        return mappers.processing_job_to_domain(model) if model else None

    async def list_for_video(
        self,
        video_id: VideoId,
        *,
        limit: int = 50,
    ) -> list[ProcessingJob]:
        result = await self._session.execute(
            select(ProcessingJobModel)
            .where(ProcessingJobModel.video_id == _coerce_uuid(video_id))
            .order_by(ProcessingJobModel.created_at.desc())
            .limit(limit)
        )
        return [mappers.processing_job_to_domain(model) for model in result.scalars()]

    async def find_active(self, video_id: VideoId, job_type: str) -> ProcessingJob | None:
        result = await self._session.execute(
            select(ProcessingJobModel)
            .where(
                ProcessingJobModel.video_id == _coerce_uuid(video_id),
                ProcessingJobModel.job_type == job_type,
                ProcessingJobModel.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
            )
            .order_by(ProcessingJobModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.processing_job_to_domain(model) if model else None

    async def update(self, job: ProcessingJob) -> None:
        model = await self._session.get(ProcessingJobModel, _coerce_uuid(job.id))
        if model is None:
            raise LookupError(f"Processing job {job.id} is not persisted.")
        mappers.apply_processing_job_to_model(job, model)
        await self._session.flush()


class SqlTrackingDatasetRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, dataset: TrackingDataset) -> None:
        self._session.add(mappers.tracking_dataset_to_model(dataset))
        await self._session.flush()

    async def get(self, dataset_id: TrackingDatasetId) -> TrackingDataset | None:
        model = await self._session.get(TrackingDatasetModel, _coerce_uuid(dataset_id))
        return mappers.tracking_dataset_to_domain(model) if model else None

    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackingDataset]:
        result = await self._session.execute(
            select(TrackingDatasetModel)
            .where(TrackingDatasetModel.analysis_run_id == _coerce_uuid(run_id))
            .order_by(TrackingDatasetModel.created_at.desc())
        )
        return [mappers.tracking_dataset_to_domain(model) for model in result.scalars()]

    async def update(self, dataset: TrackingDataset) -> None:
        model = await self._session.get(TrackingDatasetModel, _coerce_uuid(dataset.id))
        if model is None:
            raise LookupError(f"Tracking dataset {dataset.id} is not persisted.")
        model.frame_rate = dataset.frame_rate
        model.frame_count = dataset.frame_count
        model.object_count = dataset.object_count
        model.storage_key = dataset.storage_key
        model.provenance = dict(dataset.provenance)
        await self._session.flush()


class SqlTrackObservationRepository:
    """Batched writes and paged reads of per-frame tracking observations.

    A single match produces hundreds of thousands of rows; inserting them one at a
    time would dominate the worker's write path, and loading them all would defeat
    the point of streaming frames. Both directions are therefore bounded.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_batch(
        self,
        dataset: TrackingDataset,
        observations: list[TrackedObservation],
    ) -> int:
        if not observations:
            return 0
        self._session.add_all(
            [
                mappers.track_observation_to_model(
                    observation,
                    observation_id=uuid.uuid4(),
                    organization_id=dataset.organization_id,
                    video_id=dataset.video_id,
                    analysis_run_id=dataset.analysis_run_id,
                    dataset_id=dataset.id,
                )
                for observation in observations
            ]
        )
        await self._session.flush()
        return len(observations)

    async def list_for_run(
        self,
        run_id: AnalysisRunId,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]:
        result = await self._session.execute(
            select(TrackObservationModel)
            .where(TrackObservationModel.analysis_run_id == _coerce_uuid(run_id))
            .order_by(TrackObservationModel.frame_index, TrackObservationModel.track_id)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.track_observation_to_domain(model) for model in result.scalars()]

    async def count_for_run(self, run_id: AnalysisRunId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(TrackObservationModel)
            .where(TrackObservationModel.analysis_run_id == _coerce_uuid(run_id))
        )
        return int(result.scalar_one())

    async def distinct_track_count(self, run_id: AnalysisRunId) -> int:
        result = await self._session.execute(
            select(func.count(func.distinct(TrackObservationModel.track_id))).where(
                TrackObservationModel.analysis_run_id == _coerce_uuid(run_id)
            )
        )
        return int(result.scalar_one())

    async def list_for_track(
        self,
        run_id: AnalysisRunId,
        track_id: int,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]:
        result = await self._session.execute(
            select(TrackObservationModel)
            .where(
                TrackObservationModel.analysis_run_id == _coerce_uuid(run_id),
                TrackObservationModel.track_id == track_id,
            )
            .order_by(TrackObservationModel.frame_index)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.track_observation_to_domain(model) for model in result.scalars()]

    async def track_ids(self, run_id: AnalysisRunId) -> list[int]:
        result = await self._session.execute(
            select(TrackObservationModel.track_id)
            .where(TrackObservationModel.analysis_run_id == _coerce_uuid(run_id))
            .group_by(TrackObservationModel.track_id)
            .order_by(TrackObservationModel.track_id)
        )
        return [int(track_id) for track_id in result.scalars()]

    async def coordinate_extent(
        self, run_id: AnalysisRunId
    ) -> tuple[float, float, float, float] | None:
        result = await self._session.execute(
            select(
                func.min(TrackObservationModel.x1),
                func.min(TrackObservationModel.y1),
                func.max(TrackObservationModel.x2),
                func.max(TrackObservationModel.y2),
            ).where(TrackObservationModel.analysis_run_id == _coerce_uuid(run_id))
        )
        left, top, right, bottom = result.one()
        if left is None or top is None or right is None or bottom is None:
            return None
        return (float(left), float(top), float(right), float(bottom))


class SqlTrackMetricRepository:
    """Derived metrics for one analysis run.

    Replaced wholesale rather than appended to: a metrics job is idempotent, so a
    retry recalculates the same rows instead of duplicating them.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_for_run(
        self,
        run_id: AnalysisRunId,
        metrics: list[TrackMetricRecord],
    ) -> None:
        await self._session.execute(
            delete(TrackMetricModel).where(TrackMetricModel.analysis_run_id == _coerce_uuid(run_id))
        )
        if metrics:
            self._session.add_all([mappers.track_metric_to_model(metric) for metric in metrics])
        await self._session.flush()

    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackMetricRecord]:
        result = await self._session.execute(
            select(TrackMetricModel)
            .where(TrackMetricModel.analysis_run_id == _coerce_uuid(run_id))
            .order_by(TrackMetricModel.track_id, TrackMetricModel.metric_name)
        )
        return [mappers.track_metric_to_domain(model) for model in result.scalars()]

    async def count_for_run(self, run_id: AnalysisRunId) -> int:
        result = await self._session.execute(
            select(func.count())
            .select_from(TrackMetricModel)
            .where(TrackMetricModel.analysis_run_id == _coerce_uuid(run_id))
        )
        return int(result.scalar_one())


class SqlPerformanceMetricRepository:
    """Writes metrics in bulk.

    A single match produces thousands of metric rows; a per-row ' 'INSERT' '
    through the ORM would dominate the write path in the worker.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_many(self, metrics: list[PerformanceMetric]) -> None:
        if not metrics:
            return
        self._session.add_all(
            [
                PerformanceMetricModel(
                    organization_id=metric.organization_id,
                    analysis_run_id=metric.analysis_run_id,
                    match_id=metric.match_id,
                    player_id=metric.player_id,
                    team_id=metric.team_id,
                    scope=str(metric.scope),
                    category=str(metric.category),
                    name=metric.metric.name,
                    value=metric.metric.value,
                    unit=metric.metric.unit,
                    definition_version=metric.metric.definition_version,
                    period_label=metric.period_label,
                )
                for metric in metrics
            ]
        )
        await self._session.flush()

    async def list_for_run(self, run_id: AnalysisRunId) -> list[PerformanceMetric]:
        result = await self._session.execute(
            select(PerformanceMetricModel).where(
                PerformanceMetricModel.analysis_run_id == _coerce_uuid(run_id)
            )
        )
        return [self._row_to_domain(model) for model in result.scalars()]

    async def list_for_player(
        self,
        player_id: PlayerId,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PerformanceMetric]:
        result = await self._session.execute(
            select(PerformanceMetricModel)
            .where(PerformanceMetricModel.player_id == _coerce_uuid(player_id))
            .order_by(PerformanceMetricModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._row_to_domain(model) for model in result.scalars()]

    @staticmethod
    def _row_to_domain(model: PerformanceMetricModel) -> PerformanceMetric:
        from app.domain.analysis.ids import PerformanceMetricId
        from app.domain.analysis.metrics import MetricCategory, MetricScope
        from app.domain.shared import MetricValue

        return PerformanceMetric(
            id=PerformanceMetricId(model.id),
            organization_id=OrganizationId(model.organization_id),
            analysis_run_id=AnalysisRunId(model.analysis_run_id),
            match_id=MatchId(model.match_id) if model.match_id else None,
            player_id=PlayerId(model.player_id) if model.player_id else None,
            team_id=TeamId(model.team_id) if model.team_id else None,
            scope=MetricScope(model.scope),
            category=MetricCategory(model.category),
            metric=MetricValue(
                name=model.name,
                value=model.value,
                unit=model.unit,
                definition_version=model.definition_version,
            ),
            period_label=model.period_label,
        )


class SqlReportRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, report: Report) -> None:
        self._session.add(mappers.report_to_model(report))
        await self._session.flush()

    async def get(self, report_id: ReportId) -> Report | None:
        model = await self._session.get(ReportModel, _coerce_uuid(report_id))
        return mappers.report_to_domain(model) if model else None

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Report]:
        result = await self._session.execute(
            select(ReportModel)
            .where(ReportModel.organization_id == _coerce_uuid(organization_id))
            .order_by(ReportModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [mappers.report_to_domain(model) for model in result.scalars()]
