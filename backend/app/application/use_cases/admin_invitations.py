"""Administrator invitations: create, resend, revoke and accept.

The raw token exists only inside 'create_invitation' and is handed straight to
the email port. Everything persisted is the keyed hash, and the token is never a
return value, so no route can echo it and no log line can capture it by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.application.admin_authz import AdminContext, audit_event, role_privileges
from app.application.messages import admin_invitation_email
from app.application.ports.admin import (
    AdminInvitationRepository,
    AdminRepository,
    AdminRoleRepository,
)
from app.application.ports.notifications import EmailSender
from app.application.ports.repositories import SecurityEventRepository, UserRepository
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.admin.entities import (
    AdminIdentity,
    AdminInvitation,
    AdminPrivilege,
    AdminRole,
    AdminStatus,
)
from app.domain.security.entities import SecurityEventType
from app.domain.security.tokens import generate_token, hash_token
from app.domain.shared import UserId, utcnow
from app.domain.users.entities import Email

INVITATION_TTL = timedelta(days=7)


@dataclass(frozen=True, slots=True)
class IssuedInvitation:
    """An invitation and the one-time token that was mailed to its recipient."""

    invitation: AdminInvitation
    token: str


async def create_invitation(
    actor: AdminContext,
    *,
    email: str,
    role_name: str,
    roles: AdminRoleRepository,
    invitations: AdminInvitationRepository,
    security_events: SecurityEventRepository,
    email_sender: EmailSender,
    token_secret: str,
    app_base_url: str,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> IssuedInvitation:
    actor.require(AdminPrivilege.ADMINS_MANAGE)
    address = _normalize_email(email)
    role = _resolve_role(role_name)
    await _refuse_escalation(actor, role)

    outstanding = await invitations.latest_for_email(address)
    if outstanding is not None and outstanding.is_usable():
        raise ConflictError(f"An active invitation for {address} already exists.")

    await invitations.invalidate_for_email(address)

    token = generate_token()
    invitation = AdminInvitation(
        email=address,
        role=role,
        token_hash=hash_token(token, secret=token_secret),
        expires_at=utcnow() + INVITATION_TTL,
        invited_by=actor.admin.user_id,
    )
    await invitations.add(invitation, role_id=await _role_id(role, roles=roles))

    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_INVITATION_CREATED,
            actor=actor.admin.user_id,
            metadata={"email": address, "role": str(role)},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    await email_sender.send(
        admin_invitation_email(
            to=address,
            role=str(role),
            link=f"{app_base_url.rstrip('/')}/admin/invitation?token={token}",
        )
    )
    return IssuedInvitation(invitation=invitation, token=token)


async def resend_invitation(
    actor: AdminContext,
    invitation_id: object,
    *,
    invitations: AdminInvitationRepository,
    security_events: SecurityEventRepository,
    email_sender: EmailSender,
    token_secret: str,
    app_base_url: str,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> IssuedInvitation:
    """Issue a fresh token for an invitation that is still outstanding.

    The previous token is invalidated by rotating the stored hash, so a resend
    cannot leave two working links in circulation.
    """
    actor.require(AdminPrivilege.ADMINS_MANAGE)
    found = await invitations.get(invitation_id)
    if found is None:
        raise NotFoundError(f"Invitation {invitation_id} does not exist.")
    invitation, _ = found
    if not invitation.is_usable():
        raise ConflictError("Only an outstanding invitation can be resent.")

    token = generate_token()
    invitation.token_hash = hash_token(token, secret=token_secret)
    invitation.expires_at = utcnow() + INVITATION_TTL
    await invitations.update(invitation)
    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_INVITATION_RESENT,
            actor=actor.admin.user_id,
            metadata={"email": invitation.email, "role": str(invitation.role)},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    await email_sender.send(
        admin_invitation_email(
            to=invitation.email,
            role=str(invitation.role),
            link=f"{app_base_url.rstrip('/')}/admin/invitation?token={token}",
        )
    )
    return IssuedInvitation(invitation=invitation, token=token)


async def revoke_invitation(
    actor: AdminContext,
    invitation_id: object,
    *,
    invitations: AdminInvitationRepository,
    security_events: SecurityEventRepository,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AdminInvitation:
    actor.require(AdminPrivilege.ADMINS_MANAGE)
    found = await invitations.get(invitation_id)
    if found is None:
        raise NotFoundError(f"Invitation {invitation_id} does not exist.")
    invitation, _ = found
    if invitation.is_revoked:
        raise ConflictError("Invitation is already revoked.")
    if invitation.is_accepted:
        raise ConflictError("Invitation has already been accepted.")

    invitation.revoke()
    await invitations.update(invitation)
    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_INVITATION_REVOKED,
            actor=actor.admin.user_id,
            metadata={"email": invitation.email},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    return invitation


@dataclass(frozen=True, slots=True)
class AcceptedInvitation:
    admin: AdminIdentity
    email: str


async def accept_invitation(
    *,
    token: str,
    user_id: UserId,
    invitations: AdminInvitationRepository,
    admins: AdminRepository,
    roles: AdminRoleRepository,
    users: UserRepository,
    security_events: SecurityEventRepository,
    token_secret: str,
    ip_prefix: str | None = None,
    user_agent: str | None = None,
) -> AcceptedInvitation:
    """Convert an invitation into an invited administrator record.

    The record is created as INVITED, never ACTIVE: acceptance proves the holder
    of the token, not that they have enrolled a second factor. Activation is a
    separate step so a valid link alone can never produce administrative access.
    """
    candidate = hash_token(token, secret=token_secret)
    found = await invitations.get_by_token_hash(candidate)
    if found is None:
        raise NotFoundError("This invitation is not valid.")
    invitation, role_id = found
    if invitation.is_revoked or invitation.is_accepted or invitation.is_expired():
        raise ConflictError("This invitation is no longer valid.")

    account = await users.get(user_id)
    if account is None:
        raise NotFoundError("The accepting account does not exist.")
    if account.email.value != invitation.email:
        raise ConflictError("This invitation was issued to a different address.")
    if await admins.get_by_user(user_id) is not None:
        raise ConflictError("This account is already an administrator.")

    admin = AdminIdentity(
        user_id=user_id,
        status=AdminStatus(AdminStatus.INVITED),
        mfa_enrolled_at=None,
    )
    await admins.add(admin)
    await roles.assign(admin.id, invitation.role, assigned_by=invitation.invited_by)
    del role_id

    invitation.accept()
    await invitations.update(invitation)
    await security_events.add(
        audit_event(
            SecurityEventType.ADMIN_INVITATION_ACCEPTED,
            actor=user_id,
            target_admin_id=admin.id,
            metadata={"email": invitation.email, "role": str(invitation.role)},
            ip_prefix=ip_prefix,
            user_agent=user_agent,
        )
    )
    return AcceptedInvitation(admin=admin, email=invitation.email)


def _normalize_email(value: str) -> str:
    try:
        return Email(value).value
    except ValueError as exc:
        raise ValidationError("A valid email address is required.") from exc


def _resolve_role(name: str) -> AdminRole:
    try:
        return AdminRole(name)
    except ValueError as exc:
        raise ValidationError(f"Unknown administrative role: {name!r}.") from exc


async def _role_id(role: AdminRole, *, roles: AdminRoleRepository) -> object:
    """The catalogue id for a role, so the invitation row holds a real foreign key."""
    resolved = await roles.id_for_role(role)
    if resolved is None:
        raise ValidationError(f"Administrative role {role} is not in the catalogue.")
    return resolved


async def _refuse_escalation(actor: AdminContext, role: AdminRole) -> None:
    if actor.is_superadmin:
        return
    if str(role) == AdminRole.SUPERADMIN:
        raise ConflictError("Only a superadmin may invite a superadmin.")
    missing = role_privileges(role) - actor.privileges
    if missing:
        raise ConflictError(
            f"Role {role} grants privileges the actor does not hold: {sorted(missing)}."
        )
