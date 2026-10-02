"""SQLAlchemy repository implementations.

Each repository is a thin translation between a domain entity and a session; no
business rules live here. Every organization-scoped read filters by organization,
and entities are returned rather than ORM models.
"""

from __future__ import annotations

import builtins
import uuid
from datetime import date, datetime
from typing import cast

from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.admin.entities import (
    AdminId,
    AdminIdentity,
    AdminInvitation,
    AdminMfaChallenge,
    AdminPrivilege,
    AdminRole,
)
from app.domain.analysis.entities import AnalysisRun
from app.domain.analysis.metrics import PerformanceMetric
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.matches.entities import Match
from app.domain.metrics.types import TrackMetricRecord
from app.domain.organizations.entities import Organization, OrganizationMembership
from app.domain.players.entities import Player
from app.domain.reports.entities import Report
from app.domain.security.entities import (
    Challenge,
    ChallengeKind,
    OtpChallenge,
    OtpPurpose,
    SecurityEvent,
    SecurityEventType,
    Session,
)
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
    AdminInvitationModel,
    AdminMfaChallengeModel,
    AdminMfaCredentialModel,
    AdminPrivilegeGrantModel,
    AdminPrivilegeModel,
    AdminRecoveryCodeModel,
    AdminRoleAssignmentModel,
    AdminRoleModel,
    AdminRolePrivilegeModel,
    AnalysisRunModel,
    MatchModel,
    OrganizationMembershipModel,
    OrganizationModel,
    OtpChallengeModel,
    PerformanceMetricModel,
    PlatformAdminModel,
    PlayerModel,
    ProcessingJobModel,
    ReportModel,
    SecurityChallengeModel,
    SecurityEventModel,
    SessionModel,
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


_ADMIN_EVENT_TYPES = tuple(
    event_type
    for event_type in SecurityEventType.ALLOWED
    if event_type.startswith("ADMIN_")
)


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

    async def add_membership(self, membership: OrganizationMembership) -> None:
        self._session.add(mappers.membership_to_model(membership))
        await self._session.flush()

    async def list_for_user(self, user_id: UserId) -> builtins.list[OrganizationMembership]:
        result = await self._session.execute(
            select(OrganizationMembershipModel)
            .where(OrganizationMembershipModel.user_id == _coerce_uuid(user_id))
            .order_by(OrganizationMembershipModel.created_at)
        )
        return [mappers.membership_to_domain(model) for model in result.scalars()]

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

    async def update(self, user: User) -> None:
        model = await self._session.get(UserModel, _coerce_uuid(user.id))
        if model is None:
            raise LookupError(f"User {user.id} is not persisted.")
        mappers.apply_user_to_model(user, model)
        await self._session.flush()


class SqlSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, session: Session, *, token_hash: str) -> None:
        self._session.add(mappers.session_to_model(session, token_hash=token_hash))
        await self._session.flush()

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        result = await self._session.execute(
            select(SessionModel).where(SessionModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return mappers.session_to_domain(model) if model else None

    async def get_for_user(self, session_id: object, user_id: UserId) -> Session | None:
        result = await self._session.execute(
            select(SessionModel).where(
                SessionModel.id == _coerce_uuid(session_id),
                SessionModel.user_id == _coerce_uuid(user_id),
            )
        )
        model = result.scalar_one_or_none()
        return mappers.session_to_domain(model) if model else None

    async def list_for_user(self, user_id: UserId) -> list[Session]:
        result = await self._session.execute(
            select(SessionModel)
            .where(SessionModel.user_id == _coerce_uuid(user_id))
            .order_by(SessionModel.created_at.desc())
        )
        return [mappers.session_to_domain(model) for model in result.scalars()]

    async def update(self, session: Session) -> None:
        model = await self._session.get(SessionModel, _coerce_uuid(session.id))
        if model is None:
            raise LookupError(f"Session {session.id} is not persisted.")
        mappers.apply_session_to_model(session, model)
        await self._session.flush()

    async def revoke_all_for_user(
        self,
        user_id: UserId,
        *,
        except_session_id: object = None,
    ) -> int:
        statement = (
            update(SessionModel)
            .where(
                SessionModel.user_id == _coerce_uuid(user_id),
                SessionModel.revoked_at.is_(None),
            )
            .values(revoked_at=func.now())
        )
        if except_session_id is not None:
            statement = statement.where(SessionModel.id != _coerce_uuid(except_session_id))
        result = await self._session.execute(statement)
        await self._session.flush()
        return int(cast(CursorResult, result).rowcount or 0)


class SqlSecurityChallengeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, challenge: Challenge) -> None:
        self._session.add(mappers.challenge_to_model(challenge))
        await self._session.flush()

    async def get_by_token_hash(self, token_hash: str) -> Challenge | None:
        result = await self._session.execute(
            select(SecurityChallengeModel).where(SecurityChallengeModel.token_hash == token_hash)
        )
        model = result.scalar_one_or_none()
        return mappers.challenge_to_domain(model) if model else None

    async def consume(self, challenge: Challenge) -> None:
        model = await self._session.get(SecurityChallengeModel, _coerce_uuid(challenge.id))
        if model is None:
            raise LookupError(f"Challenge {challenge.id} is not persisted.")
        model.consumed_at = challenge.consumed_at or func.now()
        await self._session.flush()

    async def invalidate_active(self, user_id: UserId, kind: ChallengeKind) -> int:
        result = await self._session.execute(
            update(SecurityChallengeModel)
            .where(
                SecurityChallengeModel.user_id == _coerce_uuid(user_id),
                SecurityChallengeModel.kind == str(kind),
                SecurityChallengeModel.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
        )
        await self._session.flush()
        return int(cast(CursorResult, result).rowcount or 0)

    async def latest_for_user(self, user_id: UserId, kind: ChallengeKind) -> Challenge | None:
        result = await self._session.execute(
            select(SecurityChallengeModel)
            .where(
                SecurityChallengeModel.user_id == _coerce_uuid(user_id),
                SecurityChallengeModel.kind == str(kind),
            )
            .order_by(SecurityChallengeModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.challenge_to_domain(model) if model else None


class SqlOtpChallengeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, challenge: OtpChallenge) -> None:
        self._session.add(mappers.otp_challenge_to_model(challenge))
        await self._session.flush()

    async def latest_for_user(self, user_id: UserId, purpose: OtpPurpose) -> OtpChallenge | None:
        result = await self._session.execute(
            select(OtpChallengeModel)
            .where(
                OtpChallengeModel.user_id == _coerce_uuid(user_id),
                OtpChallengeModel.purpose == str(purpose),
            )
            .order_by(OtpChallengeModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        return mappers.otp_challenge_to_domain(model) if model else None

    async def update(self, challenge: OtpChallenge) -> None:
        model = await self._session.get(OtpChallengeModel, _coerce_uuid(challenge.id))
        if model is None:
            raise LookupError(f"OTP challenge {challenge.id} is not persisted.")
        model.attempts = challenge.attempts
        model.consumed_at = challenge.consumed_at
        await self._session.flush()

    async def invalidate_active(self, user_id: UserId, purpose: OtpPurpose) -> int:
        result = await self._session.execute(
            update(OtpChallengeModel)
            .where(
                OtpChallengeModel.user_id == _coerce_uuid(user_id),
                OtpChallengeModel.purpose == str(purpose),
                OtpChallengeModel.consumed_at.is_(None),
            )
            .values(consumed_at=func.now())
        )
        await self._session.flush()
        return int(cast(CursorResult, result).rowcount or 0)


class SqlSecurityEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: SecurityEvent) -> None:
        self._session.add(mappers.security_event_to_model(event))
        await self._session.flush()

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: SecurityEventType | None = None,
    ) -> list[SecurityEvent]:
        statement = select(SecurityEventModel).where(
            SecurityEventModel.user_id == _coerce_uuid(user_id)
        )
        if event_type is not None:
            statement = statement.where(SecurityEventModel.event_type == str(event_type))
        result = await self._session.execute(
            statement.order_by(SecurityEventModel.created_at.desc()).limit(limit).offset(offset)
        )
        return [mappers.security_event_to_domain(model) for model in result.scalars()]

    async def count_recent(
        self,
        user_id: UserId | None,
        event_type: str,
        *,
        since: object,
    ) -> int:
        statement = (
            select(func.count())
            .select_from(SecurityEventModel)
            .where(
                SecurityEventModel.event_type == str(event_type),
                SecurityEventModel.created_at >= since,
            )
        )
        if user_id is not None:
            statement = statement.where(SecurityEventModel.user_id == _coerce_uuid(user_id))
        result = await self._session.execute(statement)
        return int(result.scalar_one())

    async def list_administrative(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[SecurityEvent]:
        statement = select(SecurityEventModel).where(
            SecurityEventModel.event_type.in_(_ADMIN_EVENT_TYPES)
        )
        if event_type is not None:
            statement = statement.where(SecurityEventModel.event_type == str(event_type))
        result = await self._session.execute(
            statement.order_by(SecurityEventModel.created_at.desc(), SecurityEventModel.id)
            .limit(limit)
            .offset(offset)
        )
        return [mappers.security_event_to_domain(model) for model in result.scalars()]


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

    async def update(self, report: Report) -> None:
        model = await self._session.get(ReportModel, _coerce_uuid(report.id))
        if model is None:
            raise LookupError(f"Report {report.id} is not persisted.")
        mappers.apply_report_to_model(report, model)
        await self._session.flush()

    async def find_for_run(
        self,
        organization_id: OrganizationId,
        run_id: AnalysisRunId,
    ) -> Report | None:
        """The run-scoped report for an analysis run, if one exists.

        The scope is a column, so this is an indexed lookup rather than a scan of
        the organization's reports. Only a report scoped to the run alone is its
        report: a match- or team-scoped report lists no run here.
        """
        result = await self._session.execute(
            select(ReportModel)
            .where(
                ReportModel.organization_id == _coerce_uuid(organization_id),
                ReportModel.analysis_run_id == _coerce_uuid(run_id),
                ReportModel.match_id.is_(None),
                ReportModel.team_id.is_(None),
            )
            .order_by(ReportModel.created_at.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
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


class SqlAdminRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, admin: AdminIdentity) -> None:
        self._session.add(mappers.admin_to_model(admin))
        await self._session.flush()

    async def get(self, admin_id: object) -> AdminIdentity | None:
        model = await self._session.get(PlatformAdminModel, _coerce_uuid(admin_id))
        return mappers.admin_to_domain(model) if model else None

    async def get_by_user(self, user_id: UserId) -> AdminIdentity | None:
        result = await self._session.execute(
            select(PlatformAdminModel).where(PlatformAdminModel.user_id == _coerce_uuid(user_id))
        )
        model = result.scalar_one_or_none()
        return mappers.admin_to_domain(model) if model else None

    async def update(self, admin: AdminIdentity) -> None:
        model = await self._session.get(PlatformAdminModel, _coerce_uuid(admin.id))
        if model is None:
            raise LookupError(f"Administrator {admin.id} is not persisted.")
        mappers.apply_admin_to_model(admin, model)
        await self._session.flush()

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminIdentity]:
        result = await self._session.execute(
            select(PlatformAdminModel)
            .order_by(PlatformAdminModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [mappers.admin_to_domain(model) for model in result.scalars()]


class SqlAdminRoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_name(self, name: str) -> AdminRole | None:
        model = await self._session.scalar(
            select(AdminRoleModel).where(AdminRoleModel.name == name)
        )
        return AdminRole(model.name) if model else None

    async def id_for_role(self, role: AdminRole) -> object | None:
        model = await self._session.scalar(
            select(AdminRoleModel).where(AdminRoleModel.name == str(role))
        )
        return model.id if model else None

    async def list(self) -> builtins.list[AdminRole]:
        result = await self._session.execute(select(AdminRoleModel))
        return [AdminRole(model.name) for model in result.scalars()]

    async def roles_for_admin(self, admin_id: object) -> builtins.list[AdminRole]:
        result = await self._session.execute(
            select(AdminRoleModel)
            .join(AdminRoleAssignmentModel, AdminRoleAssignmentModel.role_id == AdminRoleModel.id)
            .where(AdminRoleAssignmentModel.admin_id == _coerce_uuid(admin_id))
        )
        return [AdminRole(model.name) for model in result.scalars()]

    async def assign(
        self,
        admin_id: object,
        role: AdminRole,
        *,
        assigned_by: UserId | None,
    ) -> None:
        role_model = await self._role_row(role)
        self._session.add(
            AdminRoleAssignmentModel(
                admin_id=_coerce_uuid(admin_id),
                role_id=role_model.id,
                assigned_by=assigned_by,
            )
        )
        await self._session.flush()

    async def unassign(self, admin_id: object, role: AdminRole) -> None:
        role_model = await self._role_row(role)
        await self._session.execute(
            delete(AdminRoleAssignmentModel).where(
                AdminRoleAssignmentModel.admin_id == _coerce_uuid(admin_id),
                AdminRoleAssignmentModel.role_id == role_model.id,
            )
        )

    async def _role_row(self, role: AdminRole) -> AdminRoleModel:
        model = await self._session.scalar(
            select(AdminRoleModel).where(AdminRoleModel.name == str(role))
        )
        if model is None:
            raise LookupError(f"Administrative role {role} is not in the catalogue.")
        return model


class SqlAdminPrivilegeRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self) -> builtins.list[AdminPrivilege]:
        result = await self._session.execute(select(AdminPrivilegeModel))
        return [AdminPrivilege(model.name) for model in result.scalars()]

    async def privileges_for_admin(self, admin_id: object) -> builtins.list[AdminPrivilege]:
        through_roles = (
            select(AdminRolePrivilegeModel.privilege_id)
            .join(
                AdminRoleAssignmentModel,
                AdminRoleAssignmentModel.role_id == AdminRolePrivilegeModel.role_id,
            )
            .where(AdminRoleAssignmentModel.admin_id == _coerce_uuid(admin_id))
        )
        direct = select(AdminPrivilegeGrantModel.privilege_id).where(
            AdminPrivilegeGrantModel.admin_id == _coerce_uuid(admin_id)
        )
        result = await self._session.execute(
            select(AdminPrivilegeModel).where(
                AdminPrivilegeModel.id.in_(through_roles.union(direct))
            )
        )
        return [AdminPrivilege(model.name) for model in result.scalars()]

    async def grant(
        self,
        admin_id: object,
        privilege: AdminPrivilege,
        *,
        granted_by: UserId | None,
    ) -> None:
        self._session.add(
            AdminPrivilegeGrantModel(
                admin_id=_coerce_uuid(admin_id),
                privilege_id=await self._privilege_id(privilege),
                granted_by=granted_by,
            )
        )
        await self._session.flush()

    async def revoke(self, admin_id: object, privilege: AdminPrivilege) -> None:
        await self._session.execute(
            delete(AdminPrivilegeGrantModel).where(
                AdminPrivilegeGrantModel.admin_id == _coerce_uuid(admin_id),
                AdminPrivilegeGrantModel.privilege_id == await self._privilege_id(privilege),
            )
        )

    async def _privilege_id(self, privilege: AdminPrivilege) -> uuid.UUID:
        model = await self._session.scalar(
            select(AdminPrivilegeModel.id).where(AdminPrivilegeModel.name == str(privilege))
        )
        if model is None:
            raise LookupError(f"Privilege {privilege} is not in the catalogue.")
        return model


class SqlAdminInvitationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, invitation: AdminInvitation, *, role_id: object) -> None:
        self._session.add(mappers.admin_invitation_to_model(invitation, role_id=role_id))
        await self._session.flush()

    async def get(self, invitation_id: object) -> tuple[AdminInvitation, object] | None:
        row = (
            await self._session.execute(
                select(AdminInvitationModel, AdminRoleModel.name)
                .join(AdminRoleModel, AdminRoleModel.id == AdminInvitationModel.role_id)
                .where(AdminInvitationModel.id == _coerce_uuid(invitation_id))
            )
        ).first()
        return self._to_domain(*row) if row else None

    async def get_by_token_hash(self, token_hash: str) -> tuple[AdminInvitation, object] | None:
        row = (
            await self._session.execute(
                select(AdminInvitationModel, AdminRoleModel.name)
                .join(AdminRoleModel, AdminRoleModel.id == AdminInvitationModel.role_id)
                .where(AdminInvitationModel.token_hash == token_hash)
            )
        ).first()
        return self._to_domain(*row) if row else None

    async def latest_for_email(self, email: str) -> AdminInvitation | None:
        row = (
            await self._session.execute(
                select(AdminInvitationModel, AdminRoleModel.name)
                .join(AdminRoleModel, AdminRoleModel.id == AdminInvitationModel.role_id)
                .where(AdminInvitationModel.email == email)
                .order_by(AdminInvitationModel.created_at.desc())
                .limit(1)
            )
        ).first()
        return self._to_domain(*row)[0] if row else None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminInvitation]:
        result = await self._session.execute(
            select(AdminInvitationModel, AdminRoleModel.name)
            .join(AdminRoleModel, AdminRoleModel.id == AdminInvitationModel.role_id)
            .order_by(AdminInvitationModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return [self._to_domain(model, role_name)[0] for model, role_name in result.all()]

    async def update(self, invitation: AdminInvitation) -> None:
        model = await self._session.get(AdminInvitationModel, _coerce_uuid(invitation.id))
        if model is None:
            raise LookupError(f"Invitation {invitation.id} is not persisted.")
        model.accepted_at = invitation.accepted_at
        model.revoked_at = invitation.revoked_at
        await self._session.flush()

    async def invalidate_for_email(self, email: str) -> int:
        result = await self._session.execute(
            update(AdminInvitationModel)
            .where(
                AdminInvitationModel.email == email,
                AdminInvitationModel.revoked_at.is_(None),
                AdminInvitationModel.accepted_at.is_(None),
            )
            .values(revoked_at=func.now())
        )
        await self._session.flush()
        return int(cast(CursorResult, result).rowcount or 0)

    def _to_domain(
        self, model: AdminInvitationModel, role_name: str
    ) -> tuple[AdminInvitation, object]:
        return (
            mappers.admin_invitation_to_domain(model, role_name=role_name),
            model.role_id,
        )


class SqlAdminMfaRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def set_secret(self, admin_id: object, *, secret_encrypted: str) -> None:
        admin_uuid = _coerce_uuid(admin_id)
        model = await self._session.scalar(
            select(AdminMfaCredentialModel).where(AdminMfaCredentialModel.admin_id == admin_uuid)
        )
        if model is None:
            self._session.add(
                AdminMfaCredentialModel(admin_id=admin_uuid, secret_encrypted=secret_encrypted)
            )
        else:
            model.secret_encrypted = secret_encrypted
        await self._session.flush()

    async def get_secret(self, admin_id: object) -> str | None:
        model = await self._session.scalar(
            select(AdminMfaCredentialModel.secret_encrypted).where(
                AdminMfaCredentialModel.admin_id == _coerce_uuid(admin_id)
            )
        )
        return model

    async def confirm(self, admin_id: object) -> None:
        await self._session.execute(
            update(AdminMfaCredentialModel)
            .where(AdminMfaCredentialModel.admin_id == _coerce_uuid(admin_id))
            .values(confirmed_at=func.now())
        )
        await self._session.flush()

    async def is_confirmed(self, admin_id: object) -> bool:
        confirmed_at = await self._session.scalar(
            select(AdminMfaCredentialModel.confirmed_at).where(
                AdminMfaCredentialModel.admin_id == _coerce_uuid(admin_id)
            )
        )
        return confirmed_at is not None

    async def replace_recovery_codes(self, admin_id: object, *, code_hashes: list[str]) -> None:
        admin_uuid = _coerce_uuid(admin_id)
        await self._session.execute(
            delete(AdminRecoveryCodeModel).where(AdminRecoveryCodeModel.admin_id == admin_uuid)
        )
        self._session.add_all(
            AdminRecoveryCodeModel(admin_id=admin_uuid, code_hash=code_hash)
            for code_hash in code_hashes
        )
        await self._session.flush()

    async def consume_recovery_code(self, admin_id: object, *, code_hash: str) -> bool:
        model = await self._session.scalar(
            select(AdminRecoveryCodeModel).where(
                AdminRecoveryCodeModel.admin_id == _coerce_uuid(admin_id),
                AdminRecoveryCodeModel.code_hash == code_hash,
                AdminRecoveryCodeModel.used_at.is_(None),
            )
        )
        if model is None:
            return False
        model.used_at = func.now()
        await self._session.flush()
        return True

    async def clear(self, admin_id: object) -> None:
        admin_uuid = _coerce_uuid(admin_id)
        await self._session.execute(
            delete(AdminRecoveryCodeModel).where(AdminRecoveryCodeModel.admin_id == admin_uuid)
        )
        await self._session.execute(
            delete(AdminMfaCredentialModel).where(AdminMfaCredentialModel.admin_id == admin_uuid)
        )
        await self._session.flush()

    async def start_challenge(
        self,
        admin_id: object,
        *,
        session_id: object,
        expires_at: object,
        max_attempts: int,
    ) -> None:
        from app.domain.admin.entities import AdminMfaChallenge

        challenge = AdminMfaChallenge(
            admin_id=AdminId(_coerce_uuid(admin_id)),
            session_id=_coerce_uuid(session_id),
            expires_at=cast(datetime, expires_at),
            max_attempts=max_attempts,
        )
        self._session.add(mappers.admin_mfa_challenge_to_model(challenge))
        await self._session.flush()

    async def get_challenge(self, admin_id: object, session_id: object) -> AdminMfaChallenge | None:
        model = await self._session.scalar(
            select(AdminMfaChallengeModel).where(
                AdminMfaChallengeModel.admin_id == _coerce_uuid(admin_id),
                AdminMfaChallengeModel.session_id == _coerce_uuid(session_id),
                AdminMfaChallengeModel.satisfied_at.is_(None),
                AdminMfaChallengeModel.expires_at > func.now(),
                AdminMfaChallengeModel.attempts < AdminMfaChallengeModel.max_attempts,
            )
        )
        return mappers.admin_mfa_challenge_to_domain(model) if model else None

    async def record_challenge_attempt(self, challenge_id: object, *, attempts: int) -> None:
        await self._session.execute(
            update(AdminMfaChallengeModel)
            .where(AdminMfaChallengeModel.id == _coerce_uuid(challenge_id))
            .values(attempts=attempts)
        )
        await self._session.flush()

    async def satisfy_challenge(self, challenge_id: object) -> None:
        await self._session.execute(
            update(AdminMfaChallengeModel)
            .where(AdminMfaChallengeModel.id == _coerce_uuid(challenge_id))
            .values(satisfied_at=func.now())
        )
        await self._session.flush()
