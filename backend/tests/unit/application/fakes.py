"""In-memory fakes for the application-layer ports.

Fakes rather than mocks: a fake implements the port's behaviour (an object goes
in, the same object comes out) so tests assert on outcomes instead of on
interaction choreography. They also make a test that would need a database run in
microseconds.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import cast

from app.domain.admin.entities import (
    AdminId,
    AdminIdentity,
    AdminInvitation,
    AdminMfaChallenge,
    AdminPrivilege,
    AdminRole,
)
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
from tests.unit.application.security_fakes import (
    FakeChallengeRepository,
    FakeOtpChallengeRepository,
    FakeSecurityEventRepository,
    FakeSessionRepository,
)


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

    async def add_membership(self, membership: OrganizationMembership) -> None:
        self.memberships.append(membership)

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

    async def update(self, user: User) -> None:
        self._items[_key(user.id)] = user

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

    async def update(self, report: Report) -> None:
        for index, item in enumerate(self.items):
            if isinstance(item, Report) and item.id == report.id:
                self.items[index] = report
                return
        raise LookupError(f"Report {report.id} is not persisted.")

    async def find_for_run(
        self,
        organization_id: OrganizationId,
        run_id: AnalysisRunId,
    ) -> Report | None:
        for item in self.items:
            if (
                isinstance(item, Report)
                and item.organization_id == organization_id
                and item.scope.analysis_run_ids == (run_id,)
            ):
                return item
        return None

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
        self.admins = FakeAdminRepository()
        self.admin_roles = FakeAdminRoleRepository()
        self.admin_privileges = FakeAdminPrivilegeRepository()
        self.admin_invitations = FakeAdminInvitationRepository()
        self.admin_mfa = FakeAdminMfaRepository()
        self.sessions = FakeSessionRepository()
        self.challenges = FakeChallengeRepository()
        self.otp_challenges = FakeOtpChallengeRepository()
        self.security_events = FakeSecurityEventRepository()
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


class FakeAdminRepository(_FakeRepository):
    async def update(self, admin: AdminIdentity) -> None:
        self._items[_key(admin.id)] = admin

    async def get_by_user(self, user_id: UserId) -> AdminIdentity | None:
        for item in self.items:
            if isinstance(item, AdminIdentity) and item.user_id == user_id:
                return item
        return None

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminIdentity]:
        admins = [item for item in self.items if isinstance(item, AdminIdentity)]
        return admins[offset : offset + limit]


class FakeAdminRoleRepository:
    def __init__(self) -> None:
        self._assignments: dict[uuid.UUID, list[AdminRole]] = {}

    async def get_by_name(self, name: str) -> AdminRole | None:
        return AdminRole(name) if name in AdminRole.ALLOWED else None

    async def id_for_role(self, role: AdminRole) -> object | None:
        if str(role) not in AdminRole.ALLOWED:
            return None
        return uuid.uuid5(uuid.NAMESPACE_DNS, f"admin-role:{role}")

    async def list(self) -> list[AdminRole]:
        return [AdminRole(name) for name in sorted(AdminRole.ALLOWED)]

    async def roles_for_admin(self, admin_id: object) -> list[AdminRole]:
        return list(self._assignments.get(_key(admin_id), []))

    async def assign(
        self,
        admin_id: object,
        role: AdminRole,
        *,
        assigned_by: UserId | None,
    ) -> None:
        held = self._assignments.setdefault(_key(admin_id), [])
        if role not in held:
            held.append(role)

    async def unassign(self, admin_id: object, role: AdminRole) -> None:
        held = self._assignments.setdefault(_key(admin_id), [])
        if role in held:
            held.remove(role)


class FakeAdminPrivilegeRepository:
    def __init__(self) -> None:
        self._grants: dict[uuid.UUID, list[AdminPrivilege]] = {}

    async def list(self) -> list[AdminPrivilege]:
        return [AdminPrivilege(name) for name in sorted(AdminPrivilege.ALLOWED)]

    async def privileges_for_admin(self, admin_id: object) -> list[AdminPrivilege]:
        return list(self._grants.get(_key(admin_id), []))

    async def grant(
        self,
        admin_id: object,
        privilege: AdminPrivilege,
        *,
        granted_by: UserId | None,
    ) -> None:
        granted = self._grants.setdefault(_key(admin_id), [])
        if privilege not in granted:
            granted.append(privilege)

    async def revoke(self, admin_id: object, privilege: AdminPrivilege) -> None:
        granted = self._grants.setdefault(_key(admin_id), [])
        if privilege in granted:
            granted.remove(privilege)


class FakeAdminInvitationRepository(_FakeRepository):
    async def add(self, invitation: AdminInvitation, *, role_id: object) -> None:
        self._role_ids[_key(invitation.id)] = role_id
        self._items[_key(invitation.id)] = invitation
        self.added.append(invitation)

    def __init__(self) -> None:
        super().__init__()
        self._role_ids: dict[uuid.UUID, object] = {}

    async def get(self, invitation_id: object) -> tuple[AdminInvitation, object] | None:
        invitation = await super().get(invitation_id)
        if isinstance(invitation, AdminInvitation):
            return invitation, self._role_ids.get(_key(invitation.id))
        return None

    async def get_by_token_hash(self, token_hash: str) -> tuple[AdminInvitation, object] | None:
        for item in self.items:
            if isinstance(item, AdminInvitation) and item.token_hash == token_hash:
                return item, self._role_ids.get(_key(item.id))
        return None

    async def latest_for_email(self, email: str) -> AdminInvitation | None:
        candidates = [
            item for item in self.items if isinstance(item, AdminInvitation) and item.email == email
        ]
        return max(candidates, key=lambda invitation: invitation.created_at, default=None)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[AdminInvitation]:
        invitations = [item for item in self.items if isinstance(item, AdminInvitation)]
        return invitations[offset : offset + limit]

    async def update(self, invitation: AdminInvitation) -> None:
        self._items[_key(invitation.id)] = invitation

    async def invalidate_for_email(self, email: str) -> int:
        count = 0
        for item in self.items:
            if (
                isinstance(item, AdminInvitation)
                and item.email == email
                and not item.is_revoked
                and not item.is_accepted
            ):
                item.revoke()
                count += 1
        return count


class FakeAdminMfaRepository:
    def __init__(self) -> None:
        self._secrets: dict[uuid.UUID, str] = {}
        self._confirmed: set[uuid.UUID] = set()
        self._recovery_codes: dict[uuid.UUID, dict[str, bool]] = {}
        self._challenges: dict[uuid.UUID, AdminMfaChallenge] = {}

    async def set_secret(self, admin_id: object, *, secret_encrypted: str) -> None:
        self._secrets[_key(admin_id)] = secret_encrypted

    async def get_secret(self, admin_id: object) -> str | None:
        return self._secrets.get(_key(admin_id))

    async def confirm(self, admin_id: object) -> None:
        self._confirmed.add(_key(admin_id))

    async def is_confirmed(self, admin_id: object) -> bool:
        return _key(admin_id) in self._confirmed

    async def replace_recovery_codes(self, admin_id: object, *, code_hashes: list[str]) -> None:
        self._recovery_codes[_key(admin_id)] = dict.fromkeys(code_hashes, False)

    async def consume_recovery_code(self, admin_id: object, *, code_hash: str) -> bool:
        codes = self._recovery_codes.setdefault(_key(admin_id), {})
        if codes.get(code_hash) is False:
            codes[code_hash] = True
            return True
        return False

    async def clear(self, admin_id: object) -> None:
        admin_uuid = _key(admin_id)
        self._secrets.pop(admin_uuid, None)
        self._confirmed.discard(admin_uuid)
        self._recovery_codes.pop(admin_uuid, None)

    async def start_challenge(
        self,
        admin_id: object,
        *,
        session_id: object,
        expires_at: object,
        max_attempts: int,
    ) -> None:
        challenge = AdminMfaChallenge(
            admin_id=AdminId(_key(admin_id)),
            session_id=session_id,
            expires_at=cast(datetime, expires_at),
            max_attempts=max_attempts,
        )
        self._challenges[_key(admin_id)] = challenge

    async def get_challenge(self, admin_id: object, session_id: object) -> AdminMfaChallenge | None:
        challenge = self._challenges.get(_key(admin_id))
        if challenge is None or str(challenge.session_id) != str(session_id):
            return None
        if challenge.is_satisfied or challenge.is_expired() or challenge.attempts_exhausted:
            return None
        return challenge

    async def record_challenge_attempt(self, challenge_id: object, *, attempts: int) -> None:
        for challenge in self._challenges.values():
            if challenge.id == challenge_id:
                challenge.attempts = attempts

    async def satisfy_challenge(self, challenge_id: object) -> None:
        for challenge in self._challenges.values():
            if challenge.id == challenge_id:
                challenge.satisfy()
