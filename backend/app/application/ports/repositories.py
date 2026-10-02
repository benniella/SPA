"""Repository ports.

Expressed in terms of domain entities, never SQLAlchemy models or query
objects, so swapping the persistence strategy does not ripple into use cases.
Collections are paginated because these tables grow large.
"""

from __future__ import annotations

import builtins
from typing import Protocol, runtime_checkable

from app.domain.analysis.entities import AnalysisRun, AnalysisRunStatus
from app.domain.analysis.metrics import PerformanceMetric
from app.domain.jobs.entities import ProcessingJob
from app.domain.matches.entities import Match
from app.domain.metrics.types import TrackMetricRecord
from app.domain.organizations.entities import Organization, OrganizationMembership
from app.domain.players.entities import Player
from app.domain.reports.entities import Report
from app.domain.security.entities import (
    Challenge,
    OtpChallenge,
    SecurityEvent,
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


@runtime_checkable
class Repository(Protocol):
    """Marker protocol: every repository can add and resolve its aggregate."""

    async def add(self, entity: object) -> None: ...


@runtime_checkable
class OrganizationRepository(Protocol):
    async def add(self, organization: Organization) -> None: ...

    async def get(self, organization_id: OrganizationId) -> Organization | None: ...

    async def get_by_slug(self, slug: str) -> Organization | None: ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Organization]: ...

    async def delete(self, organization: Organization) -> None: ...

    async def add_membership(self, membership: OrganizationMembership) -> None: ...

    async def list_for_user(self, user_id: UserId) -> builtins.list[OrganizationMembership]: ...

    async def get_membership(
        self,
        organization_id: OrganizationId,
        user_id: UserId,
    ) -> OrganizationMembership | None: ...


@runtime_checkable
class UserRepository(Protocol):
    async def add(self, user: User) -> None: ...

    async def get(self, user_id: UserId) -> User | None: ...

    async def get_by_email(self, email: str) -> User | None: ...

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[User]: ...

    async def update(self, user: User) -> None:
        """Persist mutations made to an existing account."""


@runtime_checkable
class SessionRepository(Protocol):
    """Server-controlled sessions.

    Every read is by token hash or by (user, id) pair: a session must never be
    resolvable from an identifier alone, because that would let one account's
    session id be used to read another's session.
    """

    async def add(self, session: Session, *, token_hash: str) -> None: ...

    async def get_by_token_hash(self, token_hash: str) -> Session | None: ...

    async def get_for_user(self, session_id: object, user_id: UserId) -> Session | None: ...

    async def list_for_user(self, user_id: UserId) -> list[Session]: ...

    async def update(self, session: Session) -> None: ...

    async def revoke_all_for_user(
        self, user_id: UserId, *, except_session_id: object = None
    ) -> int:
        """Revoke every live session for a user, optionally sparing one."""


@runtime_checkable
class SecurityChallengeRepository(Protocol):
    async def add(self, challenge: Challenge) -> None: ...

    async def get_by_token_hash(self, token_hash: str) -> Challenge | None: ...

    async def consume(self, challenge: Challenge) -> None: ...

    async def invalidate_active(
        self,
        user_id: UserId,
        kind: str,
    ) -> int:
        """Consume every outstanding challenge of this kind for an account.

        Called before issuing a replacement so that a resend does not leave a
        trail of live links behind it.
        """

    async def latest_for_user(self, user_id: UserId, kind: str) -> Challenge | None:
        """The most recently issued challenge, used for the resend cooldown."""


@runtime_checkable
class OtpChallengeRepository(Protocol):
    async def add(self, challenge: OtpChallenge) -> None: ...

    async def latest_for_user(self, user_id: UserId, purpose: str) -> OtpChallenge | None: ...

    async def update(self, challenge: OtpChallenge) -> None: ...

    async def invalidate_active(self, user_id: UserId, purpose: str) -> int: ...


@runtime_checkable
class SecurityEventRepository(Protocol):
    """Append and read. Deliberately has no update or delete method."""

    async def add(self, event: SecurityEvent) -> None: ...

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[SecurityEvent]: ...

    async def list_administrative(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[SecurityEvent]:
        """Platform-wide audit records, for administrators entitled to read them."""

    async def count_recent(
        self,
        user_id: UserId | None,
        event_type: str,
        *,
        since: object,
    ) -> int:
        """How many events of this type have occurred since a moment.

        Backs the suspicious-login signal; bounded by 'since' so the count stays
        cheap on a busy table.
        """


@runtime_checkable
class TeamRepository(Protocol):
    async def add(self, team: Team) -> None: ...

    async def get(self, team_id: TeamId) -> Team | None: ...

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Team]: ...

    async def delete(self, team: Team) -> None: ...


@runtime_checkable
class PlayerRepository(Protocol):
    async def add(self, player: Player) -> None: ...

    async def get(self, player_id: PlayerId) -> Player | None: ...

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]: ...

    async def list_for_team(
        self,
        team_id: TeamId,
        *,
        on_date: object | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Player]: ...


@runtime_checkable
class MatchRepository(Protocol):
    async def add(self, match: Match) -> None: ...

    async def get(self, match_id: MatchId) -> Match | None: ...

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Match]: ...

    async def delete(self, match: Match) -> None: ...


@runtime_checkable
class VideoRepository(Protocol):
    async def add(self, video: Video) -> None: ...

    async def get(self, video_id: VideoId) -> Video | None: ...

    async def list_for_match(self, match_id: MatchId) -> list[Video]: ...

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Video]: ...

    async def update(self, video: Video) -> None:
        """Persist mutations made to an existing video."""

    async def delete(self, video: Video) -> None: ...


@runtime_checkable
class AnalysisRunRepository(Protocol):
    async def add(self, run: AnalysisRun) -> None: ...

    async def get(self, run_id: AnalysisRunId) -> AnalysisRun | None: ...

    async def list_for_video(self, video_id: VideoId) -> list[AnalysisRun]: ...

    async def list_by_status(
        self,
        status: AnalysisRunStatus,
        *,
        limit: int = 50,
    ) -> list[AnalysisRun]: ...

    async def update(self, run: AnalysisRun) -> None: ...


@runtime_checkable
class ProcessingJobRepository(Protocol):
    async def add(self, job: ProcessingJob) -> None: ...

    async def get(self, job_id: JobId) -> ProcessingJob | None: ...

    async def list_for_video(
        self,
        video_id: VideoId,
        *,
        limit: int = 50,
    ) -> list[ProcessingJob]: ...

    async def find_active(self, video_id: VideoId, job_type: str) -> ProcessingJob | None:
        """Return a queued or running job of this type for the video, if any.

        Used to make a repeated processing request a no-op rather than a second
        job: two workers racing on one video would double the compute for one
        result.
        """

    async def update(self, job: ProcessingJob) -> None: ...


@runtime_checkable
class TrackingDatasetRepository(Protocol):
    async def add(self, dataset: TrackingDataset) -> None: ...

    async def get(self, dataset_id: TrackingDatasetId) -> TrackingDataset | None: ...

    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackingDataset]: ...

    async def update(self, dataset: TrackingDataset) -> None:
        """Persist the counters and metadata written after the observations land."""


@runtime_checkable
class TrackObservationRepository(Protocol):
    """Per-frame tracking observations.

    Written in bounded batches by the worker and read back one page at a time, so
    neither side ever holds a match's full observation set in memory.
    """

    async def add_batch(
        self,
        dataset: TrackingDataset,
        observations: list[TrackedObservation],
    ) -> int: ...

    async def list_for_run(
        self,
        run_id: AnalysisRunId,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]: ...

    async def count_for_run(self, run_id: AnalysisRunId) -> int: ...

    async def distinct_track_count(self, run_id: AnalysisRunId) -> int: ...

    async def list_for_track(
        self,
        run_id: AnalysisRunId,
        track_id: int,
        *,
        limit: int = 500,
        offset: int = 0,
    ) -> list[TrackRecord]:
        """Read one track's observations in frame order.

        Scoped to a track because a run's full observation set is far too large
        to hand to a browser; the caller bounds it further with 'limit'.
        """

    async def track_ids(self, run_id: AnalysisRunId) -> list[int]:
        """Every distinct track identifier in a run, in ascending order."""

    async def coordinate_extent(
        self, run_id: AnalysisRunId
    ) -> tuple[float, float, float, float] | None:
        """The min/max observed box coordinates, or 'None' when the run is empty.

        Computed in the database so deriving frame bounds never loads the
        observation set into application memory.
        """


@runtime_checkable
class TrackMetricRepository(Protocol):
    """Derived metrics, one row per track and metric name.

    Written by the metrics stage and read whole for one run. The read path is
    bounded by the number of tracks in a run, not by the number of observations.
    """

    async def replace_for_run(
        self,
        run_id: AnalysisRunId,
        metrics: list[TrackMetricRecord],
    ) -> None:
        """Replace a run's derived metrics atomically.

        Delete-then-insert inside one transaction is what makes a retried job
        idempotent: recalculating a run yields the same rows rather than a second
        copy of them.
        """

    async def list_for_run(self, run_id: AnalysisRunId) -> list[TrackMetricRecord]: ...

    async def count_for_run(self, run_id: AnalysisRunId) -> int: ...


@runtime_checkable
class PerformanceMetricRepository(Protocol):
    async def add_many(self, metrics: list[PerformanceMetric]) -> None: ...

    async def list_for_run(self, run_id: AnalysisRunId) -> list[PerformanceMetric]: ...

    async def list_for_player(
        self,
        player_id: PlayerId,
        *,
        limit: int = 200,
        offset: int = 0,
    ) -> list[PerformanceMetric]: ...


@runtime_checkable
class ReportRepository(Protocol):
    async def add(self, report: Report) -> None: ...

    async def get(self, report_id: ReportId) -> Report | None: ...

    async def update(self, report: Report) -> None:
        """Persist mutations made to an existing report."""

    async def find_for_run(
        self,
        organization_id: OrganizationId,
        run_id: AnalysisRunId,
    ) -> Report | None:
        """The run-scoped report for an analysis run, if one exists.

        A direct lookup rather than a scan of the organization's reports: the run
        is a column, so the request path does not grow with report volume.
        """

    async def list_for_organization(
        self,
        organization_id: OrganizationId,
        *,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Report]: ...
