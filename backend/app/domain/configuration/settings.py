from __future__ import annotations

from app.domain.admin.entities import AdminPrivilege
from app.domain.configuration.entities import ConfigSection, ConfigSettingSpec, ConfigType

MAINTENANCE_ENABLED = "maintenance.enabled"
MAINTENANCE_MESSAGE = "maintenance.message"
MAINTENANCE_SUPERADMIN_BYPASS = "maintenance.superadmin_bypass"

QUOTA_STORAGE_MAX_UPLOAD_BYTES = "quotas.storage_max_upload_bytes"
QUOTA_ORGANIZATION_MAX_TEAMS = "quotas.organization_max_teams"
QUOTA_ORGANIZATION_MAX_PLAYERS = "quotas.organization_max_players"
QUOTA_RUN_MAX_CONCURRENT = "quotas.run_max_concurrent"

RATE_LIMIT_ENABLED = "rate_limits.enabled"
RATE_LIMIT_ANONYMOUS_PER_MINUTE = "rate_limits.anonymous_per_minute"
RATE_LIMIT_AUTHENTICATED_PER_MINUTE = "rate_limits.authenticated_per_minute"
RATE_LIMIT_LOGIN_PER_MINUTE = "rate_limits.login_per_minute"
RATE_LIMIT_ADMIN_PER_MINUTE = "rate_limits.admin_per_minute"
RATE_LIMIT_SENSITIVE_PER_HOUR = "rate_limits.sensitive_per_hour"

COUNTRY_POLICY_MODE = "security.country_policy_mode"
COUNTRY_ALLOWLIST = "security.country_allowlist"
COUNTRY_DENYLIST = "security.country_denylist"

SUSPICIOUS_IP_TRACKING_ENABLED = "security.suspicious_ip_tracking_enabled"
SUSPICIOUS_IP_FAILURE_THRESHOLD = "security.suspicious_ip_failure_threshold"
SUSPICIOUS_IP_WINDOW_MINUTES = "security.suspicious_ip_window_minutes"


SETTINGS: tuple[ConfigSettingSpec, ...] = (
    ConfigSettingSpec(
        key=MAINTENANCE_ENABLED,
        type=ConfigType.BOOL,
        section=ConfigSection.MAINTENANCE,
        privilege=AdminPrivilege.MAINTENANCE_MANAGE,
        default=False,
        description="Refuse ordinary application traffic and report maintenance.",
    ),
    ConfigSettingSpec(
        key=MAINTENANCE_MESSAGE,
        type=ConfigType.STRING,
        section=ConfigSection.MAINTENANCE,
        privilege=AdminPrivilege.MAINTENANCE_MANAGE,
        default="",
        description="Operator-supplied message shown to users during maintenance.",
    ),
    ConfigSettingSpec(
        key=MAINTENANCE_SUPERADMIN_BYPASS,
        type=ConfigType.BOOL,
        section=ConfigSection.MAINTENANCE,
        privilege=AdminPrivilege.MAINTENANCE_MANAGE,
        default=False,
        description="Reserved for a superadmin bypass; never enabled without MFA.",
    ),
    ConfigSettingSpec(
        key=QUOTA_STORAGE_MAX_UPLOAD_BYTES,
        type=ConfigType.INT,
        section=ConfigSection.QUOTAS,
        privilege=AdminPrivilege.CONFIGURATION_MANAGE,
        default=10 * 1024**3,
        minimum=1024 * 1024,
        maximum=1024**4,
        description="Largest single video upload accepted.",
    ),
    ConfigSettingSpec(
        key=QUOTA_ORGANIZATION_MAX_TEAMS,
        type=ConfigType.INT,
        section=ConfigSection.QUOTAS,
        privilege=AdminPrivilege.CONFIGURATION_MANAGE,
        default=100,
        minimum=1,
        maximum=10_000,
        description="Teams permitted per organization.",
    ),
    ConfigSettingSpec(
        key=QUOTA_ORGANIZATION_MAX_PLAYERS,
        type=ConfigType.INT,
        section=ConfigSection.QUOTAS,
        privilege=AdminPrivilege.CONFIGURATION_MANAGE,
        default=10_000,
        minimum=1,
        maximum=1_000_000,
        description="Players permitted per organization.",
    ),
    ConfigSettingSpec(
        key=QUOTA_RUN_MAX_CONCURRENT,
        type=ConfigType.INT,
        section=ConfigSection.QUOTAS,
        privilege=AdminPrivilege.CONFIGURATION_MANAGE,
        default=4,
        minimum=1,
        maximum=100,
        description="Simultaneous analysis runs permitted per organization.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_ENABLED,
        type=ConfigType.BOOL,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=True,
        description="Global switch for application rate limits.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_ANONYMOUS_PER_MINUTE,
        type=ConfigType.INT,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=120,
        minimum=1,
        maximum=100_000,
        description="Requests per minute for an unauthenticated client.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_AUTHENTICATED_PER_MINUTE,
        type=ConfigType.INT,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=600,
        minimum=1,
        maximum=1_000_000,
        description="Requests per minute for an authenticated client.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_LOGIN_PER_MINUTE,
        type=ConfigType.INT,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=10,
        minimum=1,
        maximum=1_000,
        description="Sign-in attempts per minute per network.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_ADMIN_PER_MINUTE,
        type=ConfigType.INT,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=300,
        minimum=1,
        maximum=100_000,
        description="Administrative requests per minute.",
    ),
    ConfigSettingSpec(
        key=RATE_LIMIT_SENSITIVE_PER_HOUR,
        type=ConfigType.INT,
        section=ConfigSection.RATE_LIMITS,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=30,
        minimum=1,
        maximum=10_000,
        description="Sensitive operations (password reset, OTP) per hour.",
    ),
    ConfigSettingSpec(
        key=COUNTRY_POLICY_MODE,
        type=ConfigType.SELECT,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default="off",
        options=("off", "allowlist", "denylist"),
        description="Whether country policy is enforced, and in which direction.",
    ),
    ConfigSettingSpec(
        key=COUNTRY_ALLOWLIST,
        type=ConfigType.STRING_LIST,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=[],
        max_items=250,
        description="ISO 3166-1 alpha-2 country codes permitted when the mode is allowlist.",
    ),
    ConfigSettingSpec(
        key=COUNTRY_DENYLIST,
        type=ConfigType.STRING_LIST,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=[],
        max_items=250,
        description="ISO 3166-1 alpha-2 country codes refused when the mode is denylist.",
    ),
    ConfigSettingSpec(
        key=SUSPICIOUS_IP_TRACKING_ENABLED,
        type=ConfigType.BOOL,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=True,
        description="Record and report repeated security failures by network.",
    ),
    ConfigSettingSpec(
        key=SUSPICIOUS_IP_FAILURE_THRESHOLD,
        type=ConfigType.INT,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=10,
        minimum=1,
        maximum=10_000,
        description="Failures from one network before it is reported suspicious.",
    ),
    ConfigSettingSpec(
        key=SUSPICIOUS_IP_WINDOW_MINUTES,
        type=ConfigType.INT,
        section=ConfigSection.SECURITY,
        privilege=AdminPrivilege.SECURITY_MANAGE,
        default=15,
        minimum=1,
        maximum=1440,
        description="Window over which those failures are counted.",
    ),
)

_INDEX: dict[str, ConfigSettingSpec] = {spec.key: spec for spec in SETTINGS}


def get_spec(key: str) -> ConfigSettingSpec | None:
    return _INDEX.get(key)


def known_keys() -> frozenset[str]:
    return frozenset(_INDEX)


def default_for(key: str) -> object:
    return _INDEX[key].default


def sections() -> tuple[ConfigSection, ...]:
    return tuple(ConfigSection)


__all__ = [
    "COUNTRY_ALLOWLIST",
    "COUNTRY_DENYLIST",
    "COUNTRY_POLICY_MODE",
    "MAINTENANCE_ENABLED",
    "MAINTENANCE_MESSAGE",
    "MAINTENANCE_SUPERADMIN_BYPASS",
    "QUOTA_ORGANIZATION_MAX_PLAYERS",
    "QUOTA_ORGANIZATION_MAX_TEAMS",
    "QUOTA_RUN_MAX_CONCURRENT",
    "QUOTA_STORAGE_MAX_UPLOAD_BYTES",
    "RATE_LIMIT_ADMIN_PER_MINUTE",
    "RATE_LIMIT_ANONYMOUS_PER_MINUTE",
    "RATE_LIMIT_AUTHENTICATED_PER_MINUTE",
    "RATE_LIMIT_ENABLED",
    "RATE_LIMIT_LOGIN_PER_MINUTE",
    "RATE_LIMIT_SENSITIVE_PER_HOUR",
    "SETTINGS",
    "SUSPICIOUS_IP_FAILURE_THRESHOLD",
    "SUSPICIOUS_IP_TRACKING_ENABLED",
    "SUSPICIOUS_IP_WINDOW_MINUTES",
    "default_for",
    "get_spec",
    "known_keys",
    "sections",
]
