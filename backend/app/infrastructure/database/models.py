"""SQLAlchemy persistence models.

Only the tables needed to prove the domain boundaries hold: tenancy, teams,
players, matches, videos, analysis runs and pipeline results. Per-frame
observations, metric catalogues and season models are deliberately deferred.

JSONB is used only for open-ended content (probe output, diagnostics, report
snapshots); metrics, membership windows and references are relational.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database.base import Base, TimestampMixin, uuid_primary_key


class OrganizationModel(Base, TimestampMixin):
    """A club, academy, federation or analysis workspace."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # 'unique=True, index=True' yields a single *unique index* rather than a
    # separate unique constraint plus a plain index. The migration matches this
    # exactly; the schema-drift check in CI fails if the two ever diverge.
    slug: Mapped[str] = mapped_column(String(80), nullable=False, unique=True, index=True)

    memberships: Mapped[list[OrganizationMembershipModel]] = relationship(
        back_populates="organization",
        cascade="all, delete-orphan",
    )
    teams: Mapped[list[TeamModel]] = relationship(back_populates="organization")
    players: Mapped[list[PlayerModel]] = relationship(back_populates="organization")
    matches: Mapped[list[MatchModel]] = relationship(back_populates="organization")


class UserModel(Base, TimestampMixin):
    """A person who signs in to SPA.

    ' 'email' ' is stored lower-cased by the domain value object, so the unique
    index is meaningful. ' 'password_hash' ' holds an opaque hash produced by the
    configured hasher; no plaintext credential is ever written here.
    """

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "account_status IN ('pending_verification', 'active', 'suspended', 'deactivated')",
            name="user_account_status_known",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    # As with 'organizations.slug', this is a unique index rather than a separate
    # unique constraint.
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    account_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending_verification", server_default="active"
    )
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    phone_number: Mapped[str | None] = mapped_column(String(32), nullable=True)
    phone_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    memberships: Mapped[list[OrganizationMembershipModel]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    sessions: Mapped[list[SessionModel]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class OrganizationMembershipModel(Base, TimestampMixin):
    """Binds a user to an organization with a role."""

    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_org_membership_user"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Constrained in the domain (MembershipRole.ALLOWED); a check constraint here
    # keeps the database consistent if data is ever loaded out-of-band, without
    # freezing the role list into a PostgreSQL enum type.
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="viewer")

    organization: Mapped[OrganizationModel] = relationship(back_populates="memberships")
    user: Mapped[UserModel] = relationship(back_populates="memberships")


class TeamModel(Base, TimestampMixin):
    """A squad within an organization."""

    __tablename__ = "teams"
    __table_args__ = (UniqueConstraint("organization_id", "slug", name="uq_team_org_slug"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(80), nullable=False)
    sport: Mapped[str] = mapped_column(String(64), nullable=False, default="football")
    season: Mapped[str | None] = mapped_column(String(64), nullable=True)

    organization: Mapped[OrganizationModel] = relationship(back_populates="teams")
    memberships: Mapped[list[TeamMembershipModel]] = relationship(
        back_populates="team",
        cascade="all, delete-orphan",
    )


class PlayerModel(Base, TimestampMixin):
    """An athlete, owned by the organization rather than by a team."""

    __tablename__ = "players"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    # Identifier in an external squad-management system; lets ingestion match
    # players without name heuristics.
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    organization: Mapped[OrganizationModel] = relationship(back_populates="players")
    memberships: Mapped[list[TeamMembershipModel]] = relationship(
        back_populates="player",
        cascade="all, delete-orphan",
    )


class TeamMembershipModel(Base, TimestampMixin):
    """A player's registration in a team over a period of time.

    Modelled as a dated record rather than a ' 'team_id' ' column on ' 'players' '
    so that a past match resolves the squad as it actually was. Without this, a
    mid-season transfer silently rewrites history.
    """

    __tablename__ = "team_memberships"
    __table_args__ = (
        CheckConstraint(
            "left_on IS NULL OR left_on >= joined_on",
            name="membership_window_valid",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    team_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    player_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    joined_on: Mapped[date] = mapped_column(Date, nullable=False)
    left_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    shirt_number: Mapped[int | None] = mapped_column(Integer, nullable=True)

    team: Mapped[TeamModel] = relationship(back_populates="memberships")
    player: Mapped[PlayerModel] = relationship(back_populates="memberships")


class MatchModel(Base, TimestampMixin):
    """A recorded fixture.

    Home and away teams can be expressed as a foreign key *or* a plain name: SPA
    must handle opponents that do not exist as ' 'teams' ' rows, and creating
    placeholder team records for every opponent would corrupt the teams domain.
    """

    __tablename__ = "matches"
    __table_args__ = (Index("ix_matches_org_played_on", "organization_id", "played_on"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    played_on: Mapped[date] = mapped_column(Date, nullable=False)
    # Indexed because "every match this team played" is a real query, and an
    # unindexed foreign key makes it a sequential scan. PostgreSQL does not
    # create these automatically.
    home_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    away_team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True, index=True
    )
    home_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    away_team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    competition: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_home: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    venue_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    organization: Mapped[OrganizationModel] = relationship(back_populates="matches")
    videos: Mapped[list[VideoModel]] = relationship(back_populates="match")


class VideoModel(Base, TimestampMixin):
    """An uploaded recording.

    The bytes live in object storage; this row holds the pointer and the
    lifecycle state. ' 'status' ' is a constrained string in the domain, kept as a
    plain ' 'varchar' ' here so that adding a state is not a type migration.
    """

    __tablename__ = "videos"
    __table_args__ = (
        Index("ix_videos_org_status", "organization_id", "status"),
        CheckConstraint("size_bytes IS NULL OR size_bytes >= 0", name="size_non_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    # Opaque object-storage key. Unique so two videos cannot share a blob.
    # Declared unique *and* indexed so the model produces the single unique index
    # the migration creates.
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="uploaded")
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Source media characteristics, denormalised from VideoSpec: these are
    # first-class, queryable facts about the recording (a blunt "show me all
    # 60fps footage"), not open-ended metadata.
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # JSONB: raw probe/ingestion output. Its shape is owned by whatever media
    # tooling the ML pipeline uses and will change without notice, which is
    # precisely the case JSONB exists for.
    probe_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    match: Mapped[MatchModel | None] = relationship(back_populates="videos")
    analysis_runs: Mapped[list[AnalysisRunModel]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )
    processing_jobs: Mapped[list[ProcessingJobModel]] = relationship(
        back_populates="video",
        cascade="all, delete-orphan",
    )


class AnalysisRunModel(Base, TimestampMixin):
    """One execution of the processing pipeline over one video.

    This row is the *contract* between the synchronous API and the asynchronous
    worker: the API creates it and returns ' '202' '; the worker owns every
    subsequent state change.
    """

    __tablename__ = "analysis_runs"
    __table_args__ = (
        Index("ix_analysis_runs_video_created", "video_id", "created_at"),
        Index("ix_analysis_runs_org_status", "organization_id", "status"),
        CheckConstraint(
            "progress_percent >= 0 AND progress_percent <= 100",
            name="progress_within_range",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    progress_percent: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline definition and per-stage diagnostics. Both are open-ended by
    # design: the ML team must be able to add a stage and report its output
    # without an API or schema change.
    pipeline_spec: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    stage_results: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    video: Mapped[VideoModel] = relationship(back_populates="analysis_runs")
    tracking_datasets: Mapped[list[TrackingDatasetModel]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    track_observations: Mapped[list[TrackObservationModel]] = relationship(
        cascade="all, delete-orphan",
    )
    metrics: Mapped[list[PerformanceMetricModel]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )
    track_metrics: Mapped[list[TrackMetricModel]] = relationship(
        back_populates="analysis_run",
        cascade="all, delete-orphan",
    )


class ProcessingJobModel(Base, TimestampMixin):
    """The durable record of one unit of asynchronous video processing.

    This row, not the queue message, is the source of truth. The queue is an
    at-least-once notification channel; the worker reads the job here, verifies
    ownership from the database, and writes the outcome back. A redelivered
    message therefore cannot process the same work twice.
    """

    __tablename__ = "processing_jobs"
    __table_args__ = (
        Index("ix_processing_jobs_video_type_status", "video_id", "job_type", "status"),
        Index("ix_processing_jobs_org_status", "organization_id", "status"),
        CheckConstraint("attempt >= 0", name="attempt_non_negative"),
        CheckConstraint("max_attempts >= 1", name="max_attempts_positive"),
        CheckConstraint("progress >= 0 AND progress <= 100", name="job_progress_within_range"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    progress: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    video: Mapped[VideoModel] = relationship()


class TrackingDatasetModel(Base, TimestampMixin):
    """Trajectory output of one tracking stage execution.

    Immutable and versioned: re-running tracking creates a new dataset rather
    than mutating this one, so every derived metric remains reproducible.

    The per-frame observations are **not** modelled here. Their physical layout
    (columnar file in object storage vs. a partitioned observation table) depends
    on measured volumes and is the principal open decision in the platform.
    ' 'storage_key' ' and the counters below let either strategy be adopted without
    changing this row's meaning.
    """

    __tablename__ = "tracking_datasets"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    frame_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    object_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Model versions, homography matrix, pitch calibration, confidence
    # thresholds. Required to interpret the coordinates, and inherently
    # model-specific.
    provenance: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )

    analysis_run: Mapped[AnalysisRunModel] = relationship(back_populates="tracking_datasets")
    observations: Mapped[list[TrackObservationModel]] = relationship(
        back_populates="dataset",
        cascade="all, delete-orphan",
    )


class TrackObservationModel(Base, TimestampMixin):
    """One tracked object in one sampled frame, in source-image pixels.

    The per-frame counterpart to ' 'TrackingDatasetModel' ': a dataset is the
    summary row, these are the observations behind it. Written in bounded batches
    by the worker and read by frame or by track.

    Observations remain in source-image pixel space. ' 'organization_id' ' is
    denormalised from the dataset so tenancy is a single indexed predicate on the
    read path rather than a join.
    """

    __tablename__ = "tracking_observations"
    __table_args__ = (
        Index("ix_tracking_obs_dataset_frame", "dataset_id", "frame_index"),
        Index("ix_tracking_obs_dataset_track", "dataset_id", "track_id"),
        Index("ix_tracking_obs_run_frame", "analysis_run_id", "frame_index"),
        Index("ix_tracking_obs_video", "video_id"),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="observation_confidence_range"),
        CheckConstraint("frame_index >= 0", name="observation_frame_non_negative"),
        CheckConstraint("timestamp_seconds >= 0", name="observation_timestamp_non_negative"),
        CheckConstraint("x2 >= x1 AND y2 >= y1", name="observation_bbox_ordered"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracking_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    frame_index: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    class_id: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    x1: Mapped[float] = mapped_column(Float, nullable=False)
    y1: Mapped[float] = mapped_column(Float, nullable=False)
    x2: Mapped[float] = mapped_column(Float, nullable=False)
    y2: Mapped[float] = mapped_column(Float, nullable=False)

    dataset: Mapped[TrackingDatasetModel] = relationship(back_populates="observations")


class TrackMetricModel(Base, TimestampMixin):
    """One derived metric for one track, produced by the metrics stage.

    Relational rather than JSONB for the same reason ' 'performance_metrics' ' is:
    a coach will sort by distance and filter by speed, and both are queries on
    these columns. A value that could not be computed stores no number —
    ' 'availability' ' records why, so 'unavailable' is never read as zero.
    """

    __tablename__ = "track_metrics"
    __table_args__ = (
        # One value per (run, track, metric): the invariant that makes a retried
        # metric job idempotent even if it races another worker.
        UniqueConstraint(
            "analysis_run_id", "track_id", "metric_name", name="uq_track_metric_run_track_name"
        ),
        Index("ix_track_metrics_run_track", "analysis_run_id", "track_id"),
        CheckConstraint("track_id >= 0", name="track_metric_track_non_negative"),
        CheckConstraint("sample_count >= 0", name="track_metric_sample_count_non_negative"),
        CheckConstraint(
            "(availability = 'available' AND value IS NOT NULL) "
            "OR (availability = 'unavailable' AND value IS NULL)",
            name="track_metric_availability_matches_value",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    metric_name: Mapped[str] = mapped_column(String(64), nullable=False)
    space: Mapped[str] = mapped_column(String(16), nullable=False, default="source")
    unit: Mapped[str] = mapped_column(String(32), nullable=False)
    availability: Mapped[str] = mapped_column(String(16), nullable=False, default="available")
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    definition_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")

    analysis_run: Mapped[AnalysisRunModel] = relationship(back_populates="track_metrics")


class PerformanceMetricModel(Base, TimestampMixin):
    """One measured value attributed to a player, a team or a match.

    This is a **relational row, not a JSON blob**, and that is the single most
    consequential schema decision in SPA's design. Coaches will sort, filter and trend
    these values; a document blob would make "top distance covered this season"
    a full-table scan and application-side sort.

    ' 'definition_version' ' records *how* the number was computed, so metrics
    produced by different pipeline versions are never silently compared.
    """

    __tablename__ = "performance_metrics"
    __table_args__ = (
        Index("ix_metrics_org_category_name", "organization_id", "category", "name"),
        Index("ix_metrics_player_name", "player_id", "name"),
        Index("ix_metrics_match", "match_id"),
        # A metric must be attributable. Enforced in SQL as well as in the
        # domain so that a bug in a future worker cannot create orphan numbers.
        CheckConstraint(
            "(scope = 'player' AND player_id IS NOT NULL) "
            "OR (scope = 'team' AND team_id IS NOT NULL) "
            "OR (scope = 'match')",
            name="metric_scope_attribution",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Provenance: which run produced this number. NOT NULL — an untraceable
    # metric cannot be investigated when it looks wrong.
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    scope: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    definition_version: Mapped[str] = mapped_column(String(32), nullable=False, default="v1")
    # e.g. "first_half", "second_half", "full_match"
    period_label: Mapped[str | None] = mapped_column(String(64), nullable=True)

    analysis_run: Mapped[AnalysisRunModel] = relationship(back_populates="metrics")
    # No ORM relationship to ' 'TrackingDatasetModel' ' on purpose.
    #
    # A metric is attributed to an *analysis run*, not to a dataset, which is the
    # correct granularity: a run can produce more than one dataset (for example
    # re-tracking at a different frame rate), so a foreign key here would force a
    # false choice. Dataset provenance is reachable through the run, and every
    # metric already carries 'definition_version' for interpretability.
    #
    # Adding this relationship prematurely also broke the mapper: SQLAlchemy
    # could not infer the join condition, because no such column exists. Leaving
    # it out is both the simpler and the more accurate model.


class HeatmapGridModel(Base, TimestampMixin):
    """A spatial density surface over the pitch.

    Stored as a coarse numeric grid, not as an image: the grid is the data and
    rendering belongs to the frontend. ' 'cells' ' is a JSONB array because it is a
    dense, opaque matrix that is always read and written whole — the one case
    where JSONB is unambiguous, since there is no query like "find cells > 0.8".
    A player/team heatmap is a single row, not a table of cells.
    """

    __tablename__ = "heatmap_grids"
    __table_args__ = (CheckConstraint("rows > 0 AND cols > 0", name="grid_dimensions_positive"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracking_dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("tracking_datasets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="CASCADE"), nullable=True
    )
    player_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("players.id", ondelete="CASCADE"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), nullable=True
    )
    period_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rows: Mapped[int] = mapped_column(Integer, nullable=False)
    cols: Mapped[int] = mapped_column(Integer, nullable=False)
    cells: Mapped[list[float]] = mapped_column(JSONB, nullable=False)
    pitch_extent: Mapped[list[float] | None] = mapped_column(JSONB, nullable=True)


class ReportModel(Base, TimestampMixin):
    """A generated, shareable report.

    ' 'content' ' is a JSONB **snapshot** of the numbers rendered into the report.
    It is deliberately not a live view over ' 'performance_metrics' ': a report a
    coach downloaded last season must not change when the pipeline is re-run.
    """

    __tablename__ = "reports"
    __table_args__ = (Index("ix_reports_org_created", "organization_id", "created_at"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    organization_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    # Scope references. Nullable rather than polymorphic so PostgreSQL enforces
    # referential integrity for each kind of subject.
    match_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("matches.id", ondelete="SET NULL"), nullable=True
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("teams.id", ondelete="SET NULL"), nullable=True
    )
    # The run a run-scoped report describes. A column rather than a join table
    # because a report is authored against one run; a multi-run scope has no
    # meaning until a report actually aggregates several. Nullable so a
    # match- or team-scoped report remains possible.
    analysis_run_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    content: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    # Which report definition produced 'content'. Bumping it makes an old report's
    # shape unambiguous rather than silently reinterpreted.
    definition_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="v1", server_default="v1"
    )
    storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionModel(Base, TimestampMixin):
    """A server-controlled authenticated session.

    ' 'token_hash' ' is unique: the raw token exists only in the browser's cookie
    and in the request that presented it, so a database read cannot be replayed
    as a session. Revocation is a column write, which is what makes logout and
    "revoke this device" enforceable by the server rather than by the client.
    """

    __tablename__ = "sessions"
    __table_args__ = (
        Index("ix_sessions_user_expires", "user_id", "expires_at"),
        CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name="session_revoked_after_creation",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    # Network prefix only, truncated by the application before it is written.
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When the second factor was last satisfied on this session. Administrative
    # authorization requires it; an ordinary session leaves it NULL.
    mfa_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[UserModel] = relationship(back_populates="sessions")


class SecurityChallengeModel(Base, TimestampMixin):
    """A single-use, expiring token challenge.

    Covers email verification, an email change, password reset and account
    recovery. ' 'token_hash' ' is unique so that two live challenges can never
    share a token; ' 'consumed_at' ' records use, which is what makes a replayed
    link fail even inside its validity window.
    """

    __tablename__ = "security_challenges"
    __table_args__ = (
        Index("ix_security_challenges_user_kind", "user_id", "kind"),
        CheckConstraint(
            "kind IN ('email_verification', 'email_change', 'password_reset', 'recovery')",
            name="security_challenge_kind_known",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # The address being verified for an email change; the current address
    # otherwise.
    destination: Mapped[str | None] = mapped_column(String(320), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class OtpChallengeModel(Base, TimestampMixin):
    """A one-time code delivered to a phone number or an email address.

    Only the code's hash is stored. ' 'attempts' ' is a column rather than
    in-process state so the limit survives a restart and is shared by every
    process serving the same account.
    """

    __tablename__ = "otp_challenges"
    __table_args__ = (
        Index("ix_otp_challenges_user_purpose", "user_id", "purpose"),
        CheckConstraint("attempts >= 0", name="otp_attempts_non_negative"),
        CheckConstraint("max_attempts >= 1", name="otp_max_attempts_positive"),
        CheckConstraint(
            "purpose IN ('phone_verification', 'phone_removal', 'email_verification',"
            " 'account_recovery', 'sensitive_action')",
            name="otp_purpose_known",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    destination: Mapped[str] = mapped_column(String(320), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SecurityEventModel(Base, TimestampMixin):
    """An append-only record of a security-relevant event.

    Deliberately not user-writable. The application exposes reads only: an actor
    who could edit this table could erase the evidence of their own access, which
    defeats the point of keeping it.
    """

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_user_created", "user_id", "created_at"),
        Index("ix_security_events_type_created", "event_type", "created_at"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    # Nullable so an event about an address that does not exist (a failed sign-in
    # for an unknown email) can still be recorded without inventing a user.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    ip_prefix: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    event_metadata: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default="{}"
    )
class PlatformAdminModel(Base, TimestampMixin):
    """A user's platform-administration record.

    Keyed by user, so an administrator signs in through the same session system as
    everyone else and this table only adds platform authority. It is deliberately
    not a column on 'users': an organization owner must not become an
    administrator by any side effect.
    """

    __tablename__ = "platform_admins"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_platform_admins_user_id"),
        CheckConstraint(
            "status IN ('invited', 'active', 'suspended', 'revoked')",
            name="platform_admin_status",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="invited")
    mfa_enrolled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suspended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminRoleModel(Base, TimestampMixin):
    """The catalogue of administrative roles.

    Seeded rather than free-form, so a role name in a grant is always a role the
    platform knows. Roles carry no behaviour of their own: what a role can do is
    entirely determined by the privileges mapped to it.
    """

    __tablename__ = "admin_roles"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class AdminPrivilegeModel(Base, TimestampMixin):
    """The catalogue of platform privileges."""

    __tablename__ = "admin_privileges"

    id: Mapped[uuid.UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(300), nullable=False, default="")


class AdminRolePrivilegeModel(Base):
    """Which privileges a role grants."""

    __tablename__ = "admin_role_privileges"
    __table_args__ = (
        UniqueConstraint("role_id", "privilege_id", name="uq_admin_role_privileges_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    privilege_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_privileges.id", ondelete="CASCADE"), nullable=False, index=True
    )


class AdminRoleAssignmentModel(Base, TimestampMixin):
    """A role held by an administrator."""

    __tablename__ = "admin_role_assignments"
    __table_args__ = (
        UniqueConstraint("admin_id", "role_id", name="uq_admin_role_assignments_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assigned_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AdminPrivilegeGrantModel(Base, TimestampMixin):
    """A privilege granted directly to an administrator.

    Direct grants exist explicitly rather than being expressed as a synthetic role
    name: a grant that is not a role is auditably a grant, and revoking it cannot
    be confused with removing a job title.
    """

    __tablename__ = "admin_privilege_grants"
    __table_args__ = (
        UniqueConstraint("admin_id", "privilege_id", name="uq_admin_privilege_grants_pair"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    privilege_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_privileges.id", ondelete="CASCADE"), nullable=False, index=True
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class AdminInvitationModel(Base, TimestampMixin):
    """A single-use, expiring offer of administrative access."""

    __tablename__ = "admin_invitations"
    __table_args__ = (
        Index("ix_admin_invitations_email_created", "email", "created_at"),
        Index("ix_admin_invitations_token_hash", "token_hash", unique=True),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    role_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("admin_roles.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    invited_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminMfaCredentialModel(Base, TimestampMixin):
    """An administrator's TOTP enrolment.

    The shared secret is stored encrypted with the application secret rather than
    in plaintext, so a database read alone does not yield a working second factor.
    """

    __tablename__ = "admin_mfa_credentials"
    __table_args__ = (UniqueConstraint("admin_id", name="uq_admin_mfa_credentials_admin_id"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    secret_encrypted: Mapped[str] = mapped_column(String(512), nullable=False)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminRecoveryCodeModel(Base, TimestampMixin):
    """A single-use administrator recovery code.

    Only the hash is stored: a database read must not yield usable recovery codes.
    Regenerating the set deletes the previous rows, which is what invalidates them.
    """

    __tablename__ = "admin_recovery_codes"
    __table_args__ = (Index("ix_admin_recovery_codes_admin", "admin_id"),)

    id: Mapped[uuid.UUID] = uuid_primary_key()
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False
    )
    code_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminMfaChallengeModel(Base, TimestampMixin):
    """A short-lived MFA step-up challenge bound to a session."""

    __tablename__ = "admin_mfa_challenges"
    __table_args__ = (
        Index("ix_admin_mfa_challenges_admin", "admin_id"),
        Index("ix_admin_mfa_challenges_session", "session_id"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    admin_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("platform_admins.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    satisfied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=5)


class PlatformSettingModel(Base, TimestampMixin):
    """A stored runtime configuration value.

    Keyed by the setting's declared name. The value is JSONB because the
    declared type varies (bool, int, string, list); the declaration in
    'app.domain.configuration.settings' is what makes it typed, not the column.
    A key that is not declared is never written here.
    """

    __tablename__ = "platform_settings"

    # The declared setting name is the identity: a settings row is addressed by
    # what it configures, not by a synthetic id, and a second row for the same key
    # must be impossible rather than merely discouraged.
    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[object] = mapped_column(JSONB, nullable=False)
    changed_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class IpBlockModel(Base, TimestampMixin):
    """An auditable network block.

    'network' holds a canonical address or CIDR. 'kind' distinguishes a temporary
    block, which always carries an expiry, from a permanent one.
    """

    __tablename__ = "ip_blocks"
    __table_args__ = (
        CheckConstraint("kind IN ('temporary', 'permanent')", name="ip_block_kind"),
        Index("ix_ip_blocks_active", "removed_at", "expires_at"),
    )

    id: Mapped[uuid.UUID] = uuid_primary_key()
    network: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str] = mapped_column(String(300), nullable=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
