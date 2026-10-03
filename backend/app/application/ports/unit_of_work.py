"""Unit of work: one transaction, one commit decision.

Use cases do not know about sessions or engines: they ask for a unit of work,
work through repositories, and commit or let the context manager roll back.
"""

from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self, runtime_checkable

from app.application.ports.admin import (
    AdminInvitationRepository,
    AdminMfaRepository,
    AdminPrivilegeRepository,
    AdminRepository,
    AdminRoleRepository,
)
from app.application.ports.configuration import (
    IpBlockRepository,
    PlatformSettingRepository,
)
from app.application.ports.repositories import (
    AnalysisRunRepository,
    MatchRepository,
    OrganizationRepository,
    OtpChallengeRepository,
    PerformanceMetricRepository,
    PlayerRepository,
    ProcessingJobRepository,
    ReportRepository,
    SecurityChallengeRepository,
    SecurityEventRepository,
    SessionRepository,
    TeamRepository,
    TrackingDatasetRepository,
    TrackMetricRepository,
    TrackObservationRepository,
    UserRepository,
    VideoRepository,
)


@runtime_checkable
class UnitOfWork(Protocol):
    """A transactional scope exposing the repositories for that transaction."""

    organizations: OrganizationRepository
    users: UserRepository
    admins: AdminRepository
    admin_roles: AdminRoleRepository
    admin_privileges: AdminPrivilegeRepository
    admin_invitations: AdminInvitationRepository
    admin_mfa: AdminMfaRepository
    platform_settings: PlatformSettingRepository
    ip_blocks: IpBlockRepository
    sessions: SessionRepository
    challenges: SecurityChallengeRepository
    otp_challenges: OtpChallengeRepository
    security_events: SecurityEventRepository
    teams: TeamRepository
    players: PlayerRepository
    matches: MatchRepository
    videos: VideoRepository
    analysis_runs: AnalysisRunRepository
    processing_jobs: ProcessingJobRepository
    tracking_datasets: TrackingDatasetRepository
    track_observations: TrackObservationRepository
    track_metrics: TrackMetricRepository
    metrics: PerformanceMetricRepository
    reports: ReportRepository

    async def __aenter__(self) -> Self: ...

    # The parameter types mirror what a 'with' statement actually passes, rather
    # than the loosest 'object'. A Protocol that is narrower than its
    # implementations is unusable: the concrete class would not satisfy it.
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...

    async def commit(self) -> None: ...

    async def rollback(self) -> None: ...


class UnitOfWorkFactory(Protocol):
    """Creates unit-of-work instances, typically one per request or per job."""

    def __call__(self) -> UnitOfWork: ...
