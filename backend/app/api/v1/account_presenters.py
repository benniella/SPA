"""Read models for authentication and account security."""

from __future__ import annotations

from app.application.ports.unit_of_work import UnitOfWork
from app.domain.organizations.entities import Organization
from app.domain.security.entities import SecurityEvent, Session
from app.domain.shared import UserId
from app.domain.users.entities import User

EVENT_DESCRIPTIONS = {
    "LOGIN_SUCCESS": "Signed in",
    "LOGIN_FAILED": "Failed sign-in attempt",
    "LOGOUT": "Signed out",
    "PASSWORD_CHANGED": "Password changed",
    "PASSWORD_RESET_REQUESTED": "Password reset requested",
    "PASSWORD_RESET_COMPLETED": "Password reset completed",
    "EMAIL_VERIFICATION_REQUESTED": "Verification email sent",
    "EMAIL_VERIFIED": "Email address verified",
    "EMAIL_CHANGE_REQUESTED": "Email change requested",
    "EMAIL_CHANGED": "Email address changed",
    "PHONE_VERIFICATION_REQUESTED": "Verification code sent",
    "PHONE_VERIFIED": "Phone number verified",
    "PHONE_REMOVED": "Phone number removed",
    "SESSION_CREATED": "New session started",
    "SESSION_REVOKED": "Session ended",
    "SESSIONS_REVOKED": "Other sessions ended",
    "ACCOUNT_SUSPENDED": "Account suspended",
    "ACCOUNT_REACTIVATED": "Account reactivated",
    "RECOVERY_STARTED": "Account recovery started",
    "RECOVERY_COMPLETED": "Account recovery completed",
    "SUSPICIOUS_ACTIVITY": "Unusual sign-in activity",
}


def describe_user_agent(value: str | None) -> str:
    if not value:
        return "Unknown device"
    lowered = value.lower()

    browser = "Unknown browser"
    for needle, name in (
        ("edg/", "Edge"),
        ("opr/", "Opera"),
        ("chrome/", "Chrome"),
        ("firefox/", "Firefox"),
        ("safari/", "Safari"),
        ("curl/", "Command line"),
        ("python", "Command line"),
    ):
        if needle in lowered:
            browser = name
            break

    platform = ""
    for needle, name in (
        ("iphone", "iPhone"),
        ("ipad", "iPad"),
        ("android", "Android"),
        ("mac os", "macOS"),
        ("windows", "Windows"),
        ("linux", "Linux"),
    ):
        if needle in lowered:
            platform = name
            break

    return f"{browser} on {platform}" if platform else browser


def user_payload(user: User, organizations: list[tuple[Organization, str]]) -> dict[str, object]:
    return {
        "id": user.id,
        "email": user.email.value,
        "display_name": user.display_name,
        "account_status": str(user.account_status),
        "email_verified": user.is_email_verified,
        "phone_verified": user.is_phone_verified,
        "phone_number": user.phone_number if user.is_phone_verified else None,
        "created_at": user.created_at,
        "last_login_at": user.last_login_at,
        "organizations": [
            {
                "id": organization.id,
                "name": organization.name,
                "slug": organization.slug.value,
                "role": role,
            }
            for organization, role in organizations
        ],
    }


async def resolve_memberships(uow: UnitOfWork, user_id: UserId) -> list[tuple[Organization, str]]:
    resolved: list[tuple[Organization, str]] = []
    for membership in await uow.organizations.list_for_user(user_id):
        organization = await uow.organizations.get(membership.organization_id)
        if organization is not None:
            resolved.append((organization, str(membership.role)))
    return resolved


def session_payload(
    session: Session,
    *,
    current_session_id: object,
) -> dict[str, object]:
    return {
        "id": session.id,
        "created_at": session.created_at,
        "last_used_at": session.last_used_at,
        "expires_at": session.expires_at,
        "revoked": session.is_revoked,
        "current": str(session.id) == str(current_session_id),
        "description": describe_user_agent(session.user_agent),
        "network": session.ip_prefix,
    }


def security_event_payload(event: SecurityEvent) -> dict[str, object]:
    return {
        "id": event.id,
        "event_type": str(event.event_type),
        "created_at": event.created_at,
        "description": EVENT_DESCRIPTIONS.get(str(event.event_type), "Security activity"),
    }
