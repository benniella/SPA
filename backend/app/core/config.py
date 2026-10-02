"""Typed, validated application configuration.

Read from environment variables, and from 'backend/.env' during local
development only. Nothing here has a hard-coded secret or credential.

Every variable is namespaced with 'SPA_' so it cannot collide with an ambient
one: 'DEBUG', 'ENVIRONMENT' and similar are often already set by shells and CI
runners, and a collision either breaks startup or silently enables debug mode.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.domain.users.credentials import PasswordPolicy

BACKEND_DIR = Path(__file__).resolve().parents[2]

Environment = Literal["local", "staging", "production"]


class Settings(BaseSettings):
    """Runtime configuration for the SPA API.

    Grouped so that infrastructure concerns (storage, jobs) are already
    declared even though not all of them are wired up yet.
    """

    model_config = SettingsConfigDict(
        env_prefix="SPA_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    project_name: str = "SPA API"
    environment: Environment = "local"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # Required: no default, so a misconfigured environment fails loudly at
    # startup instead of silently falling back to an unintended database.
    database_url: str = Field(..., description="SQLAlchemy database URL.")
    db_echo: bool = False
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True

    cors_origins: str = "http://localhost:3000"
    allowed_hosts: str = "*"

    # Public base URLs. Kept in configuration rather than hard-coded in the code:
    # the production domain may change, and a reset link that points at the wrong
    # host is an account-recovery outage.
    app_base_url: str = "http://localhost:3000"
    api_base_url: str = "http://localhost:8000"

    # Authentication. 'session_secret' is required so that a misconfigured
    # deployment fails at startup instead of signing cookies with an empty key.
    session_secret: str = Field(..., min_length=32, description="Key material for token hashing.")
    session_cookie_name: str = "spa_session"
    session_ttl_hours: int = 24 * 14
    session_idle_timeout_hours: int = 24 * 7
    # 'lax' is the default because the frontend and the API are same-site in
    # production (app.spanalysis.com → api.spanalysis.com); 'strict' is available
    # for deployments that never need a cross-site entry point.
    session_cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    # Only enable this when the frontend and API are genuinely on different sites:
    # 'SameSite=None' requires 'Secure', and CSRF protection then rests on the
    # double-submit token alone.
    session_cookie_cross_site: bool = False

    csrf_cookie_name: str = "spa_csrf"
    csrf_header_name: str = "X-CSRF-Token"

    # Development-only identity header. Lets the existing integration suite and a
    # local frontend act as a chosen user without a credential exchange. There is
    # no value of this setting that enables it in production: the dependency
    # checks the environment independently.
    dev_identity_header: bool = True
    # Enables CSRF enforcement in local development as well. Off by default
    # because it makes a hand-run request need two cookies; it is always on
    # outside local, where the setting has no effect.
    csrf_enabled_locally: bool = False

    # Account security. Verification and reset tokens are hashed with
    # 'session_secret' before storage, so a database read cannot be replayed as
    # a valid link.
    email_verification_ttl_hours: int = 24 * 2
    password_reset_ttl_hours: int = 2
    email_change_ttl_hours: int = 24
    recovery_ttl_hours: int = 2
    password_min_length: int = 10
    password_max_length: int = 200

    # One-time codes for phone verification and account recovery.
    otp_ttl_minutes: int = 10
    otp_max_attempts: int = 5
    otp_resend_cooldown_seconds: int = 60
    otp_length: int = 6

    # Comma-separated origins permitted to receive a state-changing request.
    # Empty falls back to 'cors_origins', which is correct while the frontend and
    # the API are the only two clients.
    csrf_trusted_origins: str = ""

    # Suspicious-login signals. Drives an event and, past the threshold, an
    # additional verification requirement; it is not a risk score.
    suspicious_login_failure_threshold: int = 5
    suspicious_login_window_minutes: int = 15

    # Transactional email. 'console' prints the message instead of sending it, so
    # local development never needs a provider credential and never sends real
    # mail. 'smtp' sends over a plain SMTP connection; 'resend' uses the Resend
    # HTTP API.
    email_backend: Literal["console", "smtp", "resend"] = "console"
    resend_api_key: str = ""
    email_from: str = "SPA <no-reply@spa.local>"
    email_reply_to: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_starttls: bool = True

    # SMS delivery for phone verification. Empty means no SMS provider is
    # configured: a verification code is never reported as delivered when it was
    # not, and the phone endpoints answer 503 instead of pretending.
    sms_backend: Literal["none", "console", "smtp_gateway"] = "none"
    sms_sender: str = "SPA"
    # 'smtp_gateway' sends an SMS through a carrier email-to-SMS gateway, which is
    # authenticated by the same SMTP credentials as transactional email.
    sms_gateway_domain: str = ""

    # Authentication rate limiting. Counters live in KeyDB when it is reachable
    # and fall back to an in-process counter otherwise; failure to reach the
    # counter store never turns a limit off for an authentication endpoint.
    rate_limit_enabled: bool = True
    rate_limit_store: Literal["process", "keydb"] = "process"
    rate_limit_login_per_minute: int = 10
    rate_limit_login_per_account_per_minute: int = 5
    rate_limit_register_per_hour: int = 20
    rate_limit_password_reset_per_hour: int = 10
    rate_limit_resend_verification_per_hour: int = 5
    rate_limit_phone_per_hour: int = 10

    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: str = "./var/storage"
    s3_endpoint_url: str = ""
    s3_region: str = ""
    s3_bucket: str = ""
    s3_access_key_id: str = ""
    s3_secret_access_key: str = ""
    max_upload_bytes: int = 10 * 1024**3
    # Presigned URLs are short-lived: long enough for a slow uplink to finish a
    # multi-gigabyte transfer, short enough that a leaked URL is not a standing
    # grant on the object.
    upload_url_ttl_seconds: int = 3600
    download_url_ttl_seconds: int = 900

    # 'inline' records dispatches without executing them; 'queued' enqueues to
    # KeyDB for a worker process. Both are real implementations of the port —
    # 'inline' is the development default, not a no-op stub.
    job_backend: Literal["inline", "queued"] = "inline"
    # KeyDB. Ephemeral state only: the job queue and WebSocket fan-out. The
    # database remains the source of truth for every job.
    keydb_url: str = "redis://localhost:6379/0"
    keydb_database: int = 0
    # Seconds a dequeued job stays claimed before another worker may reclaim it.
    # Must exceed the longest expected job so a healthy worker is not pre-empted.
    job_visibility_timeout_seconds: int = 300
    job_max_attempts: int = 3
    worker_concurrency: int = 2

    # Realtime processing events. The host is configuration rather than a
    # hard-coded domain so a deployment can move it without a code change.
    websocket_host: str = "ws.spanalysis.com"
    websocket_allowed_origins: str = "http://localhost:3000"
    websocket_heartbeat_seconds: int = 30

    # Computer-vision pipeline. The implementation lives in 'ml/'; these are the
    # parameters the worker passes to it, centralised so no model path or
    # threshold is hard-coded. 'cv_detector' names a built-in detector, never a
    # client-supplied path, so a request cannot choose code for the worker to run.
    cv_detector: str = "hog_person"
    cv_detector_model_path: str = ""
    cv_confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    cv_device: str = "cpu"
    # Inference runs every Nth sampled frame. 1 processes every frame; the default
    # trades detection recall between frames for throughput.
    cv_frame_interval: int = Field(default=5, ge=1)
    # Rows persisted per database round-trip. Bounded so a match-long run never
    # accumulates the whole tracking dataset in memory.
    cv_track_batch_size: int = Field(default=500, ge=1)
    # Minimum box height, in pixels, for a person detection to be accepted. This
    # is detector-family configuration (a filter on the detector's output), not a
    # sport rule.
    cv_min_box_height: int = Field(default=24, ge=0)

    # Metrics. A track that disappears for longer than this is treated as a
    # tracking gap rather than continuous movement, so a re-appearing object does
    # not read as a sprint across the frame. Expressed in seconds because it is a
    # statement about tracking continuity, not about frame counts.
    metrics_max_observation_gap_seconds: float = Field(default=2.0, gt=0)
    # Observations read per database round-trip while calculating metrics. Bounded
    # so a match-long run never accumulates its whole tracking set in memory.
    metrics_batch_size: int = Field(default=2000, ge=1)

    # Visualization. A run's observation set can be enormous, so the read path
    # downsamples before it reaches the browser: the grid is a fixed size and each
    # track's path is bounded. These are response-size limits, not analytical
    # parameters — they change how much detail is drawn, never what it means.
    visualization_grid_columns: int = Field(default=48, ge=1, le=256)
    visualization_grid_rows: int = Field(default=27, ge=1, le=256)
    visualization_max_points_per_track: int = Field(default=400, ge=2)
    visualization_max_tracks: int = Field(default=100, ge=1)
    visualization_timeline_bucket_seconds: float = Field(default=5.0, gt=0)

    @property
    def allowed_video_content_types(self) -> frozenset[str]:
        """Container formats a video upload may declare.

        A product decision rather than a domain rule, so it lives with the rest
        of the transfer configuration. 'application/octet-stream' is accepted
        because many browsers and CLI clients do not know a file's type.
        """
        return frozenset(
            {
                "video/mp4",
                "video/quicktime",
                "video/x-matroska",
                "video/webm",
                "application/octet-stream",
            }
        )

    @field_validator("cv_detector")
    @classmethod
    def _normalise_detector(cls, value: str) -> str:
        return value.strip()

    @field_validator("api_v1_prefix")
    @classmethod
    def _normalise_prefix(cls, value: str) -> str:
        """Store the prefix without a trailing slash, always leading."""
        value = value.strip()
        if not value.startswith("/"):
            value = f"/{value}"
        return value.rstrip("/")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def websocket_origin_list(self) -> list[str]:
        return [
            origin.strip() for origin in self.websocket_allowed_origins.split(",") if origin.strip()
        ]

    @property
    def allowed_host_list(self) -> list[str]:
        return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]

    @property
    def is_local(self) -> bool:
        return self.environment == "local"

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def session_cookie_secure(self) -> bool:
        """Whether the session cookie carries 'Secure'.

        Derived rather than configured: a 'Secure' cookie would never be sent back
        over plain-HTTP local development, which makes the whole flow untestable
        by hand, while a non-'Secure' cookie in production is a credential leak on
        any downgrade. The environment decides, and there is no way to get it
        wrong by omission.
        """
        return self.environment != "local"

    @property
    def session_cookie_samesite_value(self) -> Literal["lax", "strict", "none"]:
        return "none" if self.session_cookie_cross_site else self.session_cookie_samesite

    @property
    def csrf_trusted_origin_list(self) -> list[str]:
        configured = self.csrf_trusted_origins or self.cors_origins
        return [origin.strip() for origin in configured.split(",") if origin.strip()]

    @property
    def password_policy(self) -> PasswordPolicy:
        return PasswordPolicy(
            min_length=self.password_min_length, max_length=self.password_max_length
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that importing modules do not re-parse the environment. Tests can
    clear the cache with ' 'get_settings.cache_clear()' '.
    """
    return Settings()  # type: ignore[call-arg]  # values come from the environment
