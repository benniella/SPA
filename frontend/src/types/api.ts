export type VideoStatus =
  "pending" | "uploading" | "uploaded" | "stored" | "processing" | "ready" | "failed";

export type AnalysisRunStatus =
  "pending" | "queued" | "running" | "succeeded" | "partially_succeeded" | "failed" | "cancelled";

export type ReportStatus = "draft" | "generating" | "ready" | "failed";

/* Pagination */

export interface PageMeta {
  limit: number;
  offset: number;
  count: number;
}

export interface Page<T> {
  items: T[];
  meta: PageMeta;
}

/* Organizations */

export interface OrganizationCreate {
  name: string;
  slug: string;
}

export interface Organization {
  id: string;
  name: string;
  slug: string;
  created_at: string;
  updated_at: string;
}

export interface UserCreate {
  email: string;
  display_name: string;
}

export interface User {
  id: string;
  email: string;
  display_name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Team {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  sport: string;
  season: string | null;
  created_at: string;
  updated_at: string;
}

export interface TeamCreate {
  organization_id: string;
  name: string;
  slug: string;
  sport?: string;
  season?: string | null;
}

export interface Player {
  id: string;
  organization_id: string;
  display_name: string;
  date_of_birth: string | null;
  external_ref: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlayerCreate {
  organization_id: string;
  display_name: string;
  date_of_birth?: string | null;
  external_ref?: string | null;
}

export interface Match {
  id: string;
  organization_id: string;
  played_on: string;
  home_team_id: string | null;
  away_team_id: string | null;
  home_team_name: string | null;
  away_team_name: string | null;
  competition: string | null;
  is_home: boolean;
  venue_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatchCreate {
  organization_id: string;
  played_on: string;
  home_team_id?: string | null;
  away_team_id?: string | null;
  home_team_name?: string | null;
  away_team_name?: string | null;
  competition?: string | null;
  is_home?: boolean;
  venue_name?: string | null;
}

export interface Video {
  id: string;
  organization_id: string;
  match_id: string | null;
  original_filename: string;
  status: VideoStatus;
  content_type: string | null;
  size_bytes: number | null;
  duration_seconds: number | null;
  frame_rate: number | null;
  width: number | null;
  height: number | null;
  codec: string | null;
  failure_reason: string | null;
  created_at: string;
  updated_at: string;
}

/** What the client needs to upload a video directly to object storage. */
export interface VideoUploadTicket {
  video_id: string;
  upload_url: string;
  storage_key: string;
  expires_in: number;
}

export interface VideoUploadRequest {
  organization_id: string;
  filename: string;
  content_type?: string | null;
  match_id?: string | null;
}

export interface VideoCompleteUploadRequest {
  organization_id: string;
  size_bytes?: number | null;
  checksum?: string | null;
}

export interface AnalysisRun {
  id: string;
  organization_id: string;
  video_id: string;
  match_id: string | null;
  status: AnalysisRunStatus;
  progress_percent: number;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Processing-job lifecycle, mirroring 'app/domain/jobs/entities.py'. */
export type ProcessingJobStatus = "queued" | "running" | "completed" | "failed";

/* Derived metrics, mirroring 'app/schemas/metrics.py'. */

export type MetricName =
  | "observation_count"
  | "duration"
  | "coverage"
  | "displacement"
  | "average_speed"
  | "peak_speed"
  | "average_acceleration"
  | "peak_acceleration"
  | "mean_confidence"
  | "min_confidence"
  | "max_confidence";

export type MetricUnit =
  "count" | "seconds" | "pixels" | "pixels_per_second" | "pixels_per_second_squared";

export type MetricSpace = "source" | "calibrated";

export interface MetricValue {
  name: MetricName;
  unit: MetricUnit;
  space: MetricSpace;
  availability: "available" | "unavailable";
  value: number | null;
  sample_count: number;
}

export interface TrackMetrics {
  track_id: number;
  space: MetricSpace;
  metrics: MetricValue[];
}

export interface AnalysisMetrics {
  analysis_run_id: string;
  organization_id: string;
  space: MetricSpace;
  definition_version: string;
  track_count: number;
  tracks: TrackMetrics[];
  generated_at: string;
}

export interface MetricsCalculation {
  analysis_run_id: string;
  job_id: string;
  status: ProcessingJobStatus;
  progress: number;
}

/* Run visualization, mirroring 'app/schemas/visualization.py'. */

export interface SourceFrame {
  width: number | null;
  height: number | null;
}

export interface TrackPoint {
  frame_index: number;
  timestamp_seconds: number;
  x: number;
  y: number;
  confidence: number;
}

export interface TrackPath {
  track_id: number;
  observation_count: number;
  downsampled: boolean;
  start_seconds: number;
  end_seconds: number;
  points: TrackPoint[];
}

export interface DensityGrid {
  columns: number;
  rows: number;
  counts: number[];
  max_count: number;
  bounds: [number, number, number, number];
  observation_count: number;
  track_count: number;
}

export interface ActivityBucket {
  index: number;
  start_seconds: number;
  end_seconds: number;
  observation_count: number;
  track_ids: number[];
}

export interface ActivityTimeline {
  bucket_seconds: number;
  start_seconds: number;
  end_seconds: number;
  max_count: number;
  buckets: ActivityBucket[];
}

export interface RunVisualization {
  analysis_run_id: string;
  organization_id: string;
  status: AnalysisRunStatus;
  space: MetricSpace;
  frame: SourceFrame;
  observation_count: number;
  track_count: number;
  paths: TrackPath[];
  density: DensityGrid;
  timeline: ActivityTimeline;
  metrics: AnalysisMetrics;
}

export interface ProcessingJob {
  id: string;
  organization_id: string;
  video_id: string;
  job_type: string;
  status: ProcessingJobStatus;
  attempt: number;
  max_attempts: number;
  progress: number;
  error: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

/** The processing state of a video, for the reconnect polling fallback. */
export interface VideoProcessing {
  video_id: string;
  video_status: VideoStatus;
  job: ProcessingJob | null;
  /** Present once an analysis run exists for the video. */
  analysis_run_id: string | null;
  /** CV counters, each 'null' until the stage that produces it has run. */
  frames_processed: number | null;
  detections: number | null;
  tracks: number | null;
}

export interface ProcessingEventMessage {
  event:
    | "processing.queued"
    | "processing.started"
    | "processing.progress"
    | "processing.completed"
    | "processing.failed";
  schema_version: number;
  job_id: string;
  video_id: string;
  status: ProcessingJobStatus;
  progress: number;
  error: string | null;
  timestamp: string;
}

/* Reports */

export interface Report {
  id: string;
  organization_id: string;
  created_by_id: string | null;
  title: string;
  status: ReportStatus;
  definition_version: string;
  analysis_run_id: string | null;
  match_id: string | null;
  team_id: string | null;
  storage_key: string | null;
  error_message: string | null;
  generated_at: string | null;
  created_at: string;
  updated_at: string;
}

export type ReportObservationType =
  | "highest_observation_count"
  | "highest_coverage"
  | "highest_displacement"
  | "highest_average_speed"
  | "highest_peak_speed"
  | "highest_peak_acceleration"
  | "longest_duration";

export interface ReportOverview {
  analysis_run_id: string;
  analysis_status: AnalysisRunStatus;
  video_id: string;
  video_filename: string;
  match_id: string | null;
  analysis_created_at: string;
  analysis_finished_at: string | null;
  source_width: number | null;
  source_height: number | null;
  observation_count: number;
  track_count: number;
  metric_definition_version: string;
  space: MetricSpace;
}

export interface ReportMetric {
  name: MetricName;
  unit: MetricUnit;
  availability: "available" | "unavailable";
  value: number | null;
  sample_count: number;
}

export interface ReportTrack {
  track_id: number;
  space: MetricSpace;
  metrics: ReportMetric[];
}

export interface ReportObservation {
  type: ReportObservationType;
  track_ids: number[];
  metric_name: MetricName;
  unit: MetricUnit;
  space: MetricSpace;
  value: number;
  message: string;
}

export interface ReportContent {
  definition_version: string;
  overview: ReportOverview;
  tracks: ReportTrack[];
  observations: ReportObservation[];
  limitations: string[];
}

export interface ReportDetail extends Report {
  content: ReportContent | null;
}

export interface HealthResponse {
  status: string;
  environment: string;
  database: string;
  version: string;
  timestamp: string;
}
/* Authentication and account security */

export interface AuthenticatedUserOrganization {
  id: string;
  name: string;
  slug: string;
  role: string;
}

export interface AuthenticatedUser {
  id: string;
  email: string;
  display_name: string;
  account_status: string;
  email_verified: boolean;
  phone_verified: boolean;
  phone_number: string | null;
  created_at: string;
  last_login_at: string | null;
  organizations: AuthenticatedUserOrganization[];
}

export interface RegisterPayload {
  email: string;
  password: string;
  display_name: string;
  organization_name: string;
  organization_slug: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegistrationAccepted {
  status: string;
  verification_required: boolean;
}

export interface MessageAccepted {
  status: string;
}

export interface SessionSummary {
  id: string;
  created_at: string;
  last_used_at: string;
  expires_at: string;
  revoked: boolean;
  current: boolean;
  description: string;
  network: string | null;
}

export interface SecurityEventRead {
  id: string;
  event_type: string;
  created_at: string;
  description: string;
}

export interface PasswordChangePayload {
  current_password: string;
  new_password: string;
}

export interface PasswordResetPayload {
  token: string;
  new_password: string;
}

export interface EmailChangePayload {
  new_email: string;
  current_password: string;
}

export interface RecoveryCompletePayload {
  email: string;
  code: string;
  new_password: string;
}

/* Platform administration, mirroring 'app/schemas/admin.py'.
   'status' is the lifecycle state the backend reports — one of 'invited',
   'active', 'suspended' or 'revoked'. It is a string rather than a union so a
   status added by a newer backend does not break an older client, matching the
   convention the API uses elsewhere. */

export interface Administrator {
  id: string;
  user_id: string;
  /** Absent when the account is gone. */
  email: string | null;
  status: string;
  /** Role names, distinct from the privilege identifiers below. */
  roles: string[];
  /** Privilege identifiers such as 'admins.read'. */
  privileges: string[];
  mfa_enrolled: boolean;
  created_at: string;
  updated_at: string;
}

export interface RoleList {
  items: string[];
}

export interface PrivilegeList {
  items: string[];
}

export interface RolesUpdatePayload {
  roles: string[];
}

export interface InvitationCreatePayload {
  email: string;
  role: string;
}

export interface InvitationCreateResult {
  invitation_id: string;
  status: string;
}

export interface InvitationResendResult {
  invitation_id: string;
  status: string;
}

export interface InvitationRevokeResult {
  invitation_id: string;
  status: string;
}

/** Acceptance leaves the record 'invited': activation requires MFA enrolment. */
export interface InvitationAccepted {
  administrator_id: string;
  status: string;
}

/** The one-time secret and URI shown during enrolment. Never persisted. */
export interface MfaEnrollmentMaterial {
  secret: string;
  provisioning_uri: string;
}

export interface MfaCodeSubmitPayload {
  code: string;
}

export interface MfaChallengeStarted {
  expires_at: string;
  max_attempts: number;
}

export interface MfaChallenge {
  challenge_id: string;
  expires_at: string;
}

/** Shown once; regenerating replaces the previous set. */
export interface MfaRecoveryCodes {
  codes: string[];
}

export interface AuditEvent {
  id: string;
  actor_id: string | null;
  event_type: string;
  metadata: Record<string, unknown>;
  created_at: string;
}