"""Mapping between domain entities and persistence models.

The only place that translates between the two, so repositories never expose a
SQLAlchemy type, and either representation can change independently.
"""

from __future__ import annotations

from typing import cast

from app.domain.admin.entities import (
    AdminId,
    AdminIdentity,
    AdminInvitation,
    AdminInvitationId,
    AdminMfaChallenge,
    AdminRole,
    AdminStatus,
)
from app.domain.analysis.entities import (
    AnalysisPipelineSpec,
    AnalysisRun,
    AnalysisRunStatus,
)
from app.domain.jobs.entities import JobStatus, ProcessingJob
from app.domain.matches.entities import Match, MatchVenue
from app.domain.metrics.types import (
    MetricAvailability,
    MetricName,
    MetricSpace,
    MetricUnit,
    MetricValue,
    TrackMetricRecord,
)
from app.domain.organizations.entities import Organization, OrganizationMembership
from app.domain.players.entities import Player, TeamMembership
from app.domain.reports.entities import Report, ReportScope
from app.domain.security.entities import (
    Challenge,
    ChallengeKind,
    OtpChallenge,
    OtpPurpose,
    SecurityEvent,
    SecurityEventId,
    SecurityEventType,
    Session,
    SessionId,
)
from app.domain.shared import (
    AnalysisRunId,
    JobId,
    MatchId,
    OrganizationId,
    PlayerId,
    ReportId,
    Slug,
    TeamId,
    TrackingDatasetId,
    TrackMetricId,
    TrackObservationId,
    UserId,
    VideoId,
    VideoSpec,
)
from app.domain.teams.entities import Team
from app.domain.tracking.entities import TrackedObservation, TrackingDataset, TrackRecord
from app.domain.users.entities import AccountStatus, Email, User
from app.domain.videos.entities import Video, VideoStatus
from app.infrastructure.database.models import (
    AdminInvitationModel,
    AdminMfaChallengeModel,
    AnalysisRunModel,
    MatchModel,
    OrganizationMembershipModel,
    OrganizationModel,
    OtpChallengeModel,
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


def _as_sequence(value: object) -> list[object]:
    """Coerce a JSONB value to a list.

    JSONB columns are typed as ' 'object' ' because their shape is owned by the
    writer. Narrowing happens here, at the boundary, rather than with a blanket
    ' 'type: ignore' ': a value that is not a list becomes an empty one instead of
    a runtime crash deep inside a mapper.
    """
    return list(value) if isinstance(value, list) else []


def _as_str_dict(value: object) -> dict[str, str]:
    """Coerce a JSONB value to a ' 'str -> str' ' mapping."""
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _as_object_dict(value: object) -> dict[str, object]:
    """Coerce a JSONB value to a ' 'str -> object' ' mapping."""
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def organization_to_domain(model: OrganizationModel) -> Organization:
    organization = Organization(
        name=model.name,
        slug=Slug(model.slug),
        id=OrganizationId(model.id),
    )
    organization.created_at = model.created_at
    organization.updated_at = model.updated_at
    return organization


def organization_to_model(entity: Organization) -> OrganizationModel:
    return OrganizationModel(id=entity.id, name=entity.name, slug=entity.slug.value)


def membership_to_domain(model: OrganizationMembershipModel) -> OrganizationMembership:
    from app.domain.organizations.entities import MembershipRole

    return OrganizationMembership(
        organization_id=OrganizationId(model.organization_id),
        user_id=UserId(model.user_id),
        role=MembershipRole(model.role),
        id=model.id,
    )


def membership_to_model(entity: OrganizationMembership) -> OrganizationMembershipModel:
    return OrganizationMembershipModel(
        organization_id=entity.organization_id,
        user_id=cast(UserId, entity.user_id),
        role=str(entity.role),
    )


def user_to_domain(model: UserModel) -> User:
    user = User(
        email=Email(model.email),
        display_name=model.display_name,
        id=UserId(model.id),
        is_active=model.is_active,
        account_status=AccountStatus(model.account_status),
        password_hash=model.password_hash,
        email_verified_at=model.email_verified_at,
        phone_number=model.phone_number,
        phone_verified_at=model.phone_verified_at,
        last_login_at=model.last_login_at,
        password_changed_at=model.password_changed_at,
    )
    user.created_at = model.created_at
    user.updated_at = model.updated_at
    return user


def user_to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id,
        email=entity.email.value,
        display_name=entity.display_name,
        is_active=entity.is_active,
        account_status=str(entity.account_status),
        password_hash=entity.password_hash,
        email_verified_at=entity.email_verified_at,
        phone_number=entity.phone_number,
        phone_verified_at=entity.phone_verified_at,
        last_login_at=entity.last_login_at,
        password_changed_at=entity.password_changed_at,
    )


def apply_user_to_model(entity: User, model: UserModel) -> None:
    """Copy mutable account state onto an existing row."""
    model.email = entity.email.value
    model.display_name = entity.display_name
    model.is_active = entity.is_active
    model.account_status = str(entity.account_status)
    model.password_hash = entity.password_hash
    model.email_verified_at = entity.email_verified_at
    model.phone_number = entity.phone_number
    model.phone_verified_at = entity.phone_verified_at
    model.last_login_at = entity.last_login_at
    model.password_changed_at = entity.password_changed_at


def session_to_domain(model: SessionModel) -> Session:
    session = Session(
        user_id=UserId(model.user_id),
        expires_at=model.expires_at,
        id=SessionId(model.id),
        last_used_at=model.last_used_at,
        revoked_at=model.revoked_at,
        user_agent=model.user_agent,
        ip_prefix=model.ip_prefix,
        mfa_verified_at=model.mfa_verified_at,
    )
    session.created_at = model.created_at
    return session


def session_to_model(entity: Session, *, token_hash: str) -> SessionModel:
    return SessionModel(
        id=entity.id,
        user_id=entity.user_id,
        token_hash=token_hash,
        expires_at=entity.expires_at,
        last_used_at=entity.last_used_at,
        revoked_at=entity.revoked_at,
        user_agent=entity.user_agent,
        ip_prefix=entity.ip_prefix,
    )


def apply_session_to_model(entity: Session, model: SessionModel) -> None:
    model.last_used_at = entity.last_used_at
    model.revoked_at = entity.revoked_at
    model.mfa_verified_at = entity.mfa_verified_at


def challenge_to_domain(model: SecurityChallengeModel) -> Challenge:
    challenge = Challenge(
        user_id=UserId(model.user_id),
        kind=str(ChallengeKind(model.kind)),
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        id=model.id,
        destination=model.destination,
        consumed_at=model.consumed_at,
    )
    challenge.created_at = model.created_at
    return challenge


def challenge_to_model(entity: Challenge) -> SecurityChallengeModel:
    return SecurityChallengeModel(
        id=entity.id,
        user_id=entity.user_id,
        kind=str(entity.kind),
        token_hash=entity.token_hash,
        destination=entity.destination,
        expires_at=entity.expires_at,
        consumed_at=entity.consumed_at,
    )


def otp_challenge_to_domain(model: OtpChallengeModel) -> OtpChallenge:
    challenge = OtpChallenge(
        user_id=UserId(model.user_id),
        purpose=str(OtpPurpose(model.purpose)),
        code_hash=model.code_hash,
        destination=model.destination,
        expires_at=model.expires_at,
        id=model.id,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        consumed_at=model.consumed_at,
    )
    challenge.created_at = model.created_at
    return challenge


def otp_challenge_to_model(entity: OtpChallenge) -> OtpChallengeModel:
    return OtpChallengeModel(
        id=entity.id,
        user_id=entity.user_id,
        purpose=str(entity.purpose),
        code_hash=entity.code_hash,
        destination=entity.destination,
        expires_at=entity.expires_at,
        attempts=entity.attempts,
        max_attempts=entity.max_attempts,
        consumed_at=entity.consumed_at,
    )


def security_event_to_model(entity: SecurityEvent) -> SecurityEventModel:
    return SecurityEventModel(
        id=entity.id,
        user_id=entity.user_id,
        event_type=str(entity.event_type),
        ip_prefix=entity.ip_prefix,
        user_agent=entity.user_agent,
        event_metadata=dict(entity.metadata),
    )


def security_event_to_domain(model: SecurityEventModel) -> SecurityEvent:
    event = SecurityEvent(
        user_id=UserId(model.user_id) if model.user_id else None,
        event_type=str(SecurityEventType(model.event_type)),
        id=SecurityEventId(model.id),
        ip_prefix=model.ip_prefix,
        user_agent=model.user_agent,
        metadata=dict(model.event_metadata or {}),
    )
    event.created_at = model.created_at
    return event


def team_to_domain(model: TeamModel) -> Team:
    team = Team(
        organization_id=OrganizationId(model.organization_id),
        name=model.name,
        slug=Slug(model.slug),
        sport=model.sport,
        id=TeamId(model.id),
        season=model.season,
    )
    team.created_at = model.created_at
    team.updated_at = model.updated_at
    return team


def team_to_model(entity: Team) -> TeamModel:
    return TeamModel(
        id=entity.id,
        organization_id=entity.organization_id,
        name=entity.name,
        slug=entity.slug.value,
        sport=entity.sport,
        season=entity.season,
    )


def player_to_domain(model: PlayerModel) -> Player:
    player = Player(
        organization_id=OrganizationId(model.organization_id),
        display_name=model.display_name,
        id=PlayerId(model.id),
        date_of_birth=model.date_of_birth,
        external_ref=model.external_ref,
    )
    player.created_at = model.created_at
    player.updated_at = model.updated_at
    return player


def player_to_model(entity: Player) -> PlayerModel:
    return PlayerModel(
        id=entity.id,
        organization_id=entity.organization_id,
        display_name=entity.display_name,
        date_of_birth=entity.date_of_birth,
        external_ref=entity.external_ref,
    )


def team_membership_to_domain(model: TeamMembershipModel) -> TeamMembership:
    return TeamMembership(
        team_id=TeamId(model.team_id),
        player_id=PlayerId(model.player_id),
        joined_on=model.joined_on,
        left_on=model.left_on,
        id=model.id,
        shirt_number=model.shirt_number,
    )


def team_membership_to_model(entity: TeamMembership) -> TeamMembershipModel:
    return TeamMembershipModel(
        team_id=entity.team_id,
        player_id=entity.player_id,
        joined_on=entity.joined_on,
        left_on=entity.left_on,
        shirt_number=entity.shirt_number,
    )


def match_to_domain(model: MatchModel) -> Match:
    match = Match(
        organization_id=OrganizationId(model.organization_id),
        played_on=model.played_on,
        id=MatchId(model.id),
        home_team_id=TeamId(model.home_team_id) if model.home_team_id else None,
        away_team_id=TeamId(model.away_team_id) if model.away_team_id else None,
        home_team_name=model.home_team_name,
        away_team_name=model.away_team_name,
        competition=model.competition,
        venue=MatchVenue(is_home=model.is_home, venue_name=model.venue_name),
    )
    match.created_at = model.created_at
    match.updated_at = model.updated_at
    return match


def match_to_model(entity: Match) -> MatchModel:
    return MatchModel(
        id=entity.id,
        organization_id=entity.organization_id,
        played_on=entity.played_on,
        home_team_id=entity.home_team_id,
        away_team_id=entity.away_team_id,
        home_team_name=entity.home_team_name,
        away_team_name=entity.away_team_name,
        competition=entity.competition,
        is_home=entity.venue.is_home,
        venue_name=entity.venue.venue_name,
    )


def video_to_domain(model: VideoModel) -> Video:
    video = Video(
        organization_id=OrganizationId(model.organization_id),
        original_filename=model.original_filename,
        storage_key=model.storage_key,
        id=VideoId(model.id),
        match_id=MatchId(model.match_id) if model.match_id else None,
        status=VideoStatus(model.status),
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        checksum=model.checksum,
        spec=VideoSpec(
            duration_seconds=model.duration_seconds,
            frame_rate=model.frame_rate,
            width=model.width,
            height=model.height,
            codec=model.codec,
        ),
        metadata=dict(model.probe_metadata or {}),
        failure_reason=model.failure_reason,
    )
    video.created_at = model.created_at
    video.updated_at = model.updated_at
    return video


def video_to_model(entity: Video) -> VideoModel:
    return VideoModel(
        id=entity.id,
        organization_id=entity.organization_id,
        match_id=entity.match_id,
        original_filename=entity.original_filename,
        storage_key=entity.storage_key,
        status=str(entity.status),
        content_type=entity.content_type,
        size_bytes=entity.size_bytes,
        checksum=entity.checksum,
        failure_reason=entity.failure_reason,
        duration_seconds=entity.spec.duration_seconds,
        frame_rate=entity.spec.frame_rate,
        width=entity.spec.width,
        height=entity.spec.height,
        codec=entity.spec.codec,
        probe_metadata=dict(entity.metadata),
    )


def apply_video_to_model(entity: Video, model: VideoModel) -> None:
    """Copy mutable video state onto an existing row.

    Used by the update path so that a status transition does not require
    deleting and re-inserting the row (which would cascade into analysis runs).
    """
    model.status = str(entity.status)
    model.size_bytes = entity.size_bytes
    model.checksum = entity.checksum
    model.failure_reason = entity.failure_reason
    model.match_id = entity.match_id
    model.duration_seconds = entity.spec.duration_seconds
    model.frame_rate = entity.spec.frame_rate
    model.width = entity.spec.width
    model.height = entity.spec.height
    model.codec = entity.spec.codec
    model.probe_metadata = dict(entity.metadata)


def analysis_run_to_domain(model: AnalysisRunModel) -> AnalysisRun:
    spec_payload = dict(model.pipeline_spec or {})
    run = AnalysisRun(
        organization_id=OrganizationId(model.organization_id),
        video_id=VideoId(model.video_id),
        id=AnalysisRunId(model.id),
        match_id=MatchId(model.match_id) if model.match_id else None,
        pipeline=AnalysisPipelineSpec(
            stages=tuple(str(stage) for stage in _as_sequence(spec_payload.get("stages"))),
            model_versions=_as_str_dict(spec_payload.get("model_versions")),
            params=_as_object_dict(spec_payload.get("params")),
        ),
        status=AnalysisRunStatus(model.status),
        progress_percent=model.progress_percent,
        started_at=model.started_at,
        finished_at=model.finished_at,
        error_message=model.error_message,
        stage_results=dict(model.stage_results or {}),
    )
    run.created_at = model.created_at
    run.updated_at = model.updated_at
    return run


def analysis_run_to_model(entity: AnalysisRun) -> AnalysisRunModel:
    return AnalysisRunModel(
        id=entity.id,
        organization_id=entity.organization_id,
        video_id=entity.video_id,
        match_id=entity.match_id,
        status=str(entity.status),
        progress_percent=entity.progress_percent,
        started_at=entity.started_at,
        finished_at=entity.finished_at,
        error_message=entity.error_message,
        pipeline_spec={
            "stages": list(entity.pipeline.stages),
            "model_versions": dict(entity.pipeline.model_versions),
            "params": dict(entity.pipeline.params),
        },
        stage_results=dict(entity.stage_results),
    )


def apply_analysis_run_to_model(entity: AnalysisRun, model: AnalysisRunModel) -> None:
    model.status = str(entity.status)
    model.progress_percent = entity.progress_percent
    model.started_at = entity.started_at
    model.finished_at = entity.finished_at
    model.error_message = entity.error_message
    model.stage_results = dict(entity.stage_results)


def processing_job_to_domain(model: ProcessingJobModel) -> ProcessingJob:
    job = ProcessingJob(
        organization_id=OrganizationId(model.organization_id),
        video_id=VideoId(model.video_id),
        job_type=model.job_type,
        id=JobId(model.id),
        status=JobStatus(model.status),
        attempt=model.attempt,
        max_attempts=model.max_attempts,
        progress=model.progress,
        error=model.error,
        started_at=model.started_at,
        completed_at=model.completed_at,
    )
    job.created_at = model.created_at
    job.updated_at = model.updated_at
    return job


def processing_job_to_model(entity: ProcessingJob) -> ProcessingJobModel:
    return ProcessingJobModel(
        id=entity.id,
        organization_id=entity.organization_id,
        video_id=entity.video_id,
        job_type=entity.job_type,
        status=str(entity.status),
        attempt=entity.attempt,
        max_attempts=entity.max_attempts,
        progress=entity.progress,
        error=entity.error,
        started_at=entity.started_at,
        completed_at=entity.completed_at,
    )


def apply_processing_job_to_model(entity: ProcessingJob, model: ProcessingJobModel) -> None:
    model.status = str(entity.status)
    model.attempt = entity.attempt
    model.max_attempts = entity.max_attempts
    model.progress = entity.progress
    model.error = entity.error
    model.started_at = entity.started_at
    model.completed_at = entity.completed_at


def tracking_dataset_to_domain(model: TrackingDatasetModel) -> TrackingDataset:
    dataset = TrackingDataset(
        organization_id=OrganizationId(model.organization_id),
        video_id=VideoId(model.video_id),
        analysis_run_id=AnalysisRunId(model.analysis_run_id),
        id=TrackingDatasetId(model.id),
        frame_rate=model.frame_rate,
        frame_count=model.frame_count,
        object_count=model.object_count,
        storage_key=model.storage_key,
        provenance=dict(model.provenance or {}),
    )
    dataset.created_at = model.created_at
    return dataset


def tracking_dataset_to_model(entity: TrackingDataset) -> TrackingDatasetModel:
    return TrackingDatasetModel(
        id=entity.id,
        organization_id=entity.organization_id,
        analysis_run_id=entity.analysis_run_id,
        video_id=entity.video_id,
        frame_rate=entity.frame_rate,
        frame_count=entity.frame_count,
        object_count=entity.object_count,
        storage_key=entity.storage_key,
        provenance=dict(entity.provenance),
    )


def track_observation_to_model(
    entity: TrackedObservation,
    *,
    observation_id: object,
    organization_id: OrganizationId,
    video_id: VideoId,
    analysis_run_id: AnalysisRunId,
    dataset_id: TrackingDatasetId,
) -> TrackObservationModel:
    return TrackObservationModel(
        id=observation_id,
        organization_id=organization_id,
        dataset_id=dataset_id,
        analysis_run_id=analysis_run_id,
        video_id=video_id,
        frame_index=entity.frame_index,
        timestamp_seconds=entity.timestamp_seconds,
        track_id=entity.track_id,
        class_id=entity.class_id,
        confidence=entity.confidence,
        x1=entity.x1,
        y1=entity.y1,
        x2=entity.x2,
        y2=entity.y2,
    )


def track_observation_to_domain(model: TrackObservationModel) -> TrackRecord:
    return TrackRecord(
        id=TrackObservationId(model.id),
        organization_id=OrganizationId(model.organization_id),
        video_id=VideoId(model.video_id),
        analysis_run_id=AnalysisRunId(model.analysis_run_id),
        observation=TrackedObservation(
            track_id=model.track_id,
            class_id=model.class_id,
            confidence=model.confidence,
            x1=model.x1,
            y1=model.y1,
            x2=model.x2,
            y2=model.y2,
            frame_index=model.frame_index,
            timestamp_seconds=model.timestamp_seconds,
        ),
        created_at=model.created_at,
    )


def track_metric_to_model(entity: TrackMetricRecord) -> TrackMetricModel:
    return TrackMetricModel(
        id=entity.id,
        organization_id=entity.organization_id,
        analysis_run_id=entity.analysis_run_id,
        track_id=entity.track_id,
        metric_name=str(entity.value.name),
        space=str(entity.space),
        unit=str(entity.value.unit),
        availability=str(entity.value.availability),
        value=entity.value.value,
        sample_count=entity.value.sample_count,
        definition_version=entity.definition_version,
    )


def track_metric_to_domain(model: TrackMetricModel) -> TrackMetricRecord:
    record = TrackMetricRecord(
        id=TrackMetricId(model.id),
        organization_id=OrganizationId(model.organization_id),
        analysis_run_id=AnalysisRunId(model.analysis_run_id),
        track_id=model.track_id,
        value=MetricValue(
            name=MetricName(model.metric_name),
            availability=MetricAvailability(model.availability),
            unit=MetricUnit(model.unit),
            value=model.value,
            sample_count=model.sample_count,
        ),
        space=MetricSpace(model.space),
        definition_version=model.definition_version,
    )
    return record


def report_to_domain(model: ReportModel) -> Report:
    from app.domain.reports.entities import ReportStatus

    report = Report(
        organization_id=OrganizationId(model.organization_id),
        title=model.title,
        scope=ReportScope(
            match_id=MatchId(model.match_id) if model.match_id else None,
            team_id=TeamId(model.team_id) if model.team_id else None,
            analysis_run_ids=(
                (AnalysisRunId(model.analysis_run_id),) if model.analysis_run_id else ()
            ),
        ),
        id=ReportId(model.id),
        created_by_id=UserId(model.created_by_id) if model.created_by_id else None,
        status=ReportStatus(model.status),
        content=dict(model.content or {}),
        definition_version=model.definition_version,
        storage_key=model.storage_key,
        error_message=model.error_message,
        generated_at=model.generated_at,
    )
    report.created_at = model.created_at
    report.updated_at = model.updated_at
    return report


def report_to_model(entity: Report) -> ReportModel:
    return ReportModel(
        id=entity.id,
        organization_id=entity.organization_id,
        created_by_id=entity.created_by_id,
        title=entity.title,
        status=str(entity.status),
        match_id=entity.scope.match_id,
        team_id=entity.scope.team_id,
        analysis_run_id=entity.scope.analysis_run_id,
        content=dict(entity.content),
        definition_version=entity.definition_version,
        storage_key=entity.storage_key,
        error_message=entity.error_message,
        generated_at=entity.generated_at,
    )


def apply_report_to_model(entity: Report, model: ReportModel) -> None:
    """Copy a mutated report's fields onto its persisted row."""
    model.title = entity.title
    model.status = str(entity.status)
    model.match_id = entity.scope.match_id
    model.team_id = entity.scope.team_id
    model.analysis_run_id = entity.scope.analysis_run_id
    model.content = dict(entity.content)
    model.definition_version = entity.definition_version
    model.storage_key = entity.storage_key
    model.error_message = entity.error_message
    model.generated_at = entity.generated_at


def admin_to_domain(model: PlatformAdminModel) -> AdminIdentity:
    return AdminIdentity(
        user_id=UserId(model.user_id),
        status=AdminStatus(model.status),
        id=AdminId(model.id),
        mfa_enrolled_at=model.mfa_enrolled_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def admin_to_model(entity: AdminIdentity) -> PlatformAdminModel:
    model = PlatformAdminModel(
        id=entity.id,
        user_id=entity.user_id,
        status=str(entity.status),
        mfa_enrolled_at=entity.mfa_enrolled_at,
    )
    _apply_admin_status_times(entity, model)
    return model


def apply_admin_to_model(entity: AdminIdentity, model: PlatformAdminModel) -> None:
    model.status = str(entity.status)
    model.mfa_enrolled_at = entity.mfa_enrolled_at
    _apply_admin_status_times(entity, model)


def _apply_admin_status_times(entity: AdminIdentity, model: PlatformAdminModel) -> None:
    status = str(entity.status)
    if status == AdminStatus.SUSPENDED and model.suspended_at is None:
        model.suspended_at = entity.updated_at
    if status == AdminStatus.REVOKED and model.revoked_at is None:
        model.revoked_at = entity.updated_at


def admin_invitation_to_domain(
    model: AdminInvitationModel,
    *,
    role_name: str,
) -> AdminInvitation:
    return AdminInvitation(
        email=model.email,
        role=AdminRole(role_name),
        token_hash=model.token_hash,
        expires_at=model.expires_at,
        invited_by=UserId(model.invited_by) if model.invited_by else None,
        id=AdminInvitationId(model.id),
        created_at=model.created_at,
        accepted_at=model.accepted_at,
        revoked_at=model.revoked_at,
    )


def admin_invitation_to_model(
    entity: AdminInvitation,
    *,
    role_id: object,
) -> AdminInvitationModel:
    return AdminInvitationModel(
        id=entity.id,
        email=entity.email,
        role_id=role_id,
        token_hash=entity.token_hash,
        invited_by=entity.invited_by,
        expires_at=entity.expires_at,
        accepted_at=entity.accepted_at,
        revoked_at=entity.revoked_at,
    )


def admin_mfa_challenge_to_domain(model: AdminMfaChallengeModel) -> AdminMfaChallenge:
    challenge = AdminMfaChallenge(
        admin_id=AdminId(model.admin_id),
        session_id=model.session_id,
        expires_at=model.expires_at,
        id=model.id,
        attempts=model.attempts,
        max_attempts=model.max_attempts,
        created_at=model.created_at,
        satisfied_at=model.satisfied_at,
    )
    return challenge


def admin_mfa_challenge_to_model(entity: AdminMfaChallenge) -> AdminMfaChallengeModel:
    return AdminMfaChallengeModel(
        id=entity.id,
        admin_id=entity.admin_id,
        session_id=entity.session_id,
        expires_at=entity.expires_at,
        satisfied_at=entity.satisfied_at,
        attempts=entity.attempts,
        max_attempts=entity.max_attempts,
    )


def apply_admin_mfa_challenge_to_model(
    entity: AdminMfaChallenge,
    model: AdminMfaChallengeModel,
) -> None:
    model.attempts = entity.attempts
    model.satisfied_at = entity.satisfied_at
