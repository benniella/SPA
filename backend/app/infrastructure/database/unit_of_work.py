"""Unit-of-work implementation over an async SQLAlchemy session.

Repositories are constructed per unit of work and share one session, so a use
case's writes commit or roll back together.
"""

from __future__ import annotations

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.database.repositories import (
    SqlAdminInvitationRepository,
    SqlAdminMfaRepository,
    SqlAdminPrivilegeRepository,
    SqlAdminRepository,
    SqlAdminRoleRepository,
    SqlAnalysisRunRepository,
    SqlMatchRepository,
    SqlOrganizationRepository,
    SqlOtpChallengeRepository,
    SqlPerformanceMetricRepository,
    SqlPlayerRepository,
    SqlProcessingJobRepository,
    SqlReportRepository,
    SqlSecurityChallengeRepository,
    SqlSecurityEventRepository,
    SqlSessionRepository,
    SqlTeamRepository,
    SqlTrackingDatasetRepository,
    SqlTrackMetricRepository,
    SqlTrackObservationRepository,
    SqlUserRepository,
    SqlVideoRepository,
)


class SqlAlchemyUnitOfWork:
    """A transaction scope over one async session.

    The repository attributes are declared here even though they are assigned in
    ' '_bind' ', because they only exist inside an ' 'async with' ' block. Declaring
    them makes that contract visible to a reader and to a type checker — the
    alternative is attributes that mysteriously do not exist yet at runtime.
    """

    organizations: SqlOrganizationRepository
    users: SqlUserRepository
    admins: SqlAdminRepository
    admin_roles: SqlAdminRoleRepository
    admin_privileges: SqlAdminPrivilegeRepository
    admin_invitations: SqlAdminInvitationRepository
    admin_mfa: SqlAdminMfaRepository
    sessions: SqlSessionRepository
    challenges: SqlSecurityChallengeRepository
    otp_challenges: SqlOtpChallengeRepository
    security_events: SqlSecurityEventRepository
    teams: SqlTeamRepository
    players: SqlPlayerRepository
    matches: SqlMatchRepository
    videos: SqlVideoRepository
    analysis_runs: SqlAnalysisRunRepository
    processing_jobs: SqlProcessingJobRepository
    tracking_datasets: SqlTrackingDatasetRepository
    track_observations: SqlTrackObservationRepository
    track_metrics: SqlTrackMetricRepository
    metrics: SqlPerformanceMetricRepository
    reports: SqlReportRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    @property
    def session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("Unit of work used outside its 'async with' block.")
        return self._session

    def _bind(self, session: AsyncSession) -> None:
        self._session = session
        self.organizations = SqlOrganizationRepository(session)
        self.users = SqlUserRepository(session)
        self.admins = SqlAdminRepository(session)
        self.admin_roles = SqlAdminRoleRepository(session)
        self.admin_privileges = SqlAdminPrivilegeRepository(session)
        self.admin_invitations = SqlAdminInvitationRepository(session)
        self.admin_mfa = SqlAdminMfaRepository(session)
        self.sessions = SqlSessionRepository(session)
        self.challenges = SqlSecurityChallengeRepository(session)
        self.otp_challenges = SqlOtpChallengeRepository(session)
        self.security_events = SqlSecurityEventRepository(session)
        self.teams = SqlTeamRepository(session)
        self.players = SqlPlayerRepository(session)
        self.matches = SqlMatchRepository(session)
        self.videos = SqlVideoRepository(session)
        self.analysis_runs = SqlAnalysisRunRepository(session)
        self.processing_jobs = SqlProcessingJobRepository(session)
        self.tracking_datasets = SqlTrackingDatasetRepository(session)
        self.track_observations = SqlTrackObservationRepository(session)
        self.track_metrics = SqlTrackMetricRepository(session)
        self.metrics = SqlPerformanceMetricRepository(session)
        self.reports = SqlReportRepository(session)

    async def __aenter__(self) -> SqlAlchemyUnitOfWork:
        self._bind(self._session_factory())
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        # Roll back anything uncommitted. A use case that raised must not leave a
        # partial write behind, and a use case that simply forgot to commit
        # should fail loudly in review rather than silently persist.
        if exc_type is not None and self._session is not None:
            await self._session.rollback()
        await self.close()

    async def commit(self) -> None:
        await self.session.commit()

    async def rollback(self) -> None:
        await self.session.rollback()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


class SqlAlchemyUnitOfWorkFactory:
    """Creates unit-of-work instances bound to the application session factory."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    def __call__(self) -> SqlAlchemyUnitOfWork:
        return SqlAlchemyUnitOfWork(self._session_factory)
