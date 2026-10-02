"""Registration, sign-in, sign-out and email verification."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.application.messages import (
    email_change_email,
    email_changed_notice,
    security_notice,
    verification_email,
)
from app.application.ports.notifications import DeliveryError, EmailSender
from app.application.ports.security import RateLimiter
from app.application.ports.unit_of_work import UnitOfWork
from app.application.security import (
    RequestContext,
    consume_challenge,
    issue_challenge,
    record_event,
)
from app.application.sessions import IssuedSession, issue_session
from app.core.config import Settings
from app.core.errors import (
    AccountNotActiveError,
    AuthenticationError,
    ConfigurationError,
    ConflictError,
    EmailDeliveryError,
    RateLimitedError,
    ValidationError,
)
from app.domain.organizations.entities import MembershipRole, Organization, OrganizationMembership
from app.domain.security.entities import ChallengeKind, SecurityEventType
from app.domain.shared import OrganizationId, Slug, UserId, utcnow
from app.domain.users.credentials import PasswordHasher, PasswordPolicy
from app.domain.users.entities import Email, User

SUSPICIOUS_WINDOW_MINUTES = 15
SUSPICIOUS_ACTIVITY_THRESHOLD = 3


@dataclass(frozen=True, slots=True)
class RegistrationResult:
    user: User
    organization_id: OrganizationId
    # True when the address already belonged to an account. The response is
    # identical either way, so this is for the caller's own logging only and must
    # never reach the client.
    already_registered: bool


def _rate_key(prefix: str, identifier: str) -> str:
    return f"spa:ratelimit:{prefix}:{identifier.lower()}"


async def _enforce(
    limiter: RateLimiter,
    key: str,
    *,
    limit: int,
    window_seconds: int,
) -> None:
    decision = await limiter.hit(key, limit=limit, window_seconds=window_seconds)
    if not decision.allowed:
        raise RateLimitedError(
            "Too many attempts. Try again shortly.",
            retry_after_seconds=decision.retry_after_seconds,
        )


async def register_user(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    password: str,
    display_name: str,
    organization_name: str,
    organization_slug: str,
    hasher: PasswordHasher,
    limiter: RateLimiter,
    client_key: str,
    email_sender: EmailSender,
    context: RequestContext | None = None,
) -> RegistrationResult:
    """Create an account and its first workspace.

    The response is deliberately identical whether or not the address was
    already registered, and no message is sent to an existing account holder
    here: confirming which addresses exist would turn registration into an
    account-enumeration oracle.
    """
    await _enforce(
        limiter,
        _rate_key("register", client_key),
        limit=settings.rate_limit_register_per_hour,
        window_seconds=3600,
    )

    policy = PasswordPolicy(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
    )
    _validate_password(policy, password)

    candidate = Email(email)
    slug = Slug(organization_slug)

    async with uow:
        existing = await uow.users.get_by_email(candidate.value)
        if existing is not None:
            # An address that already has an account is answered exactly as a new
            # one is, and no message is sent: confirming which addresses exist is
            # the whole value of probing this endpoint.
            return RegistrationResult(
                user=existing,
                organization_id=OrganizationId(existing.id),
                already_registered=True,
            )

        user = User(
            email=candidate,
            display_name=display_name.strip(),
            password_hash=hasher.hash(password),
        )
        await uow.users.add(user)

        organization = Organization(name=organization_name, slug=slug)
        await uow.organizations.add(organization)
        await uow.organizations.add_membership(
            OrganizationMembership(
                organization_id=organization.id,
                user_id=user.id,
                role=MembershipRole(MembershipRole.OWNER),
            )
        )
        token = await issue_challenge(
            uow,
            settings,
            user_id=user.id,
            kind=ChallengeKind.EMAIL_VERIFICATION,
            destination=user.email.value,
            context=context,
        )
        await uow.commit()

    await _send_verification(settings, user, token, sender=email_sender)
    return RegistrationResult(user=user, organization_id=organization.id, already_registered=False)


async def resend_verification(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    email_sender: EmailSender,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> None:
    """Issue a fresh verification challenge, if there is anything to verify.

    Always silent about the outcome: an unknown address, an already-verified
    address and a fresh challenge all produce the same success response.
    """
    await _enforce(
        limiter,
        _rate_key("resend-verification", client_key),
        limit=settings.rate_limit_resend_verification_per_hour,
        window_seconds=3600,
    )

    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None or user.is_email_verified:
            return
        token = await issue_challenge(
            uow,
            settings,
            user_id=user.id,
            kind=ChallengeKind.EMAIL_VERIFICATION,
            destination=user.email.value,
            context=context,
        )
        await uow.commit()

    await _send_verification(settings, user, token, sender=email_sender)


async def verify_email(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
    context: RequestContext | None = None,
) -> User:
    """Consume a verification challenge and activate the account."""
    async with uow:
        challenge = await consume_challenge(
            uow, settings, token=token, kind=ChallengeKind.EMAIL_VERIFICATION
        )
        user = await uow.users.get(UserId(challenge.user_id))
        if user is None:
            raise ValidationError("This link is not valid or has expired.")

        user.mark_email_verified()
        await uow.users.update(user)
        await record_event(
            uow, event_type=SecurityEventType.EMAIL_VERIFIED, user_id=user.id, context=context
        )
        await uow.commit()
    return user


async def login(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    password: str,
    hasher: PasswordHasher,
    limiter: RateLimiter,
    client_key: str,
    email_sender: EmailSender | None = None,
    context: RequestContext | None = None,
) -> IssuedSession:
    """Verify credentials and open a session.

    Failure is always the same message and the same status, whether the address
    is unknown, the password is wrong or the account may not authenticate: that
    distinction is exactly what an enumeration attempt is looking for.
    """
    await _enforce(
        limiter,
        _rate_key("login", client_key),
        limit=settings.rate_limit_login_per_minute,
        window_seconds=60,
    )
    await _enforce(
        limiter,
        _rate_key("login-account", email),
        limit=settings.rate_limit_login_per_account_per_minute,
        window_seconds=60,
    )

    async with uow:
        user = await uow.users.get_by_email(email)
        verified = (
            user is not None
            and user.has_password
            and hasher.verify(password, user.password_hash or "")
        )
        if user is None or not verified:
            await record_event(
                uow,
                event_type=SecurityEventType.LOGIN_FAILED,
                user_id=user.id if user else None,
                context=context,
            )
            await uow.commit()
            raise AuthenticationError("The email address or password is not correct.")

        if not user.can_authenticate:
            await record_event(
                uow,
                event_type=SecurityEventType.LOGIN_FAILED,
                user_id=user.id,
                context=context,
                metadata={"reason": str(user.account_status)},
            )
            await uow.commit()
            raise AccountNotActiveError("This account cannot sign in right now.")

        suspicious = await _failed_attempts_recently(uow, user.id)
        if suspicious:
            await record_event(
                uow,
                event_type=SecurityEventType.SUSPICIOUS_ACTIVITY,
                user_id=user.id,
                context=context,
                metadata={"failed_attempts": suspicious},
            )

        user.record_login()
        await uow.users.update(user)
        await record_event(
            uow, event_type=SecurityEventType.LOGIN_SUCCESS, user_id=user.id, context=context
        )
        issued = await issue_session(uow, settings, user_id=user.id, context=context)
        await uow.commit()

    await limiter.reset(_rate_key("login-account", email))

    if suspicious and email_sender is not None:
        await _notify_suspicious(settings, user, email_sender, suspicious)
    return issued


async def logout(
    uow: UnitOfWork,
    settings: Settings,
    *,
    session_token: str | None,
    user_id: UserId | None,
    context: RequestContext | None = None,
) -> None:
    """Revoke the presented session.

    Revocation is a database write, so a client that keeps its cookie still
    cannot use it. An unknown or already-revoked token is not an error: signing
    out twice is a success from the user's point of view.
    """
    from app.application.sessions import resolve_session

    if session_token is None:
        return
    async with uow:
        session = await resolve_session(uow, settings, token=session_token)
        if session is None:
            return
        session.revoke()
        await uow.sessions.update(session)
        await record_event(
            uow,
            event_type=SecurityEventType.LOGOUT,
            user_id=user_id or session.user_id,
            context=context,
        )
        await uow.commit()


async def change_email(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user: User,
    new_email: str,
    current_password: str,
    hasher: PasswordHasher,
    email_sender: EmailSender,
    context: RequestContext | None = None,
) -> None:
    """Begin an email change.

    The new address is not adopted here. Confirming it first is what stops a
    stolen session from permanently redirecting the account to an attacker's
    mailbox, and the old address is warned so its owner can object.
    """
    if not user.has_password or not hasher.verify(current_password, user.password_hash or ""):
        raise AuthenticationError("The current password is not correct.")

    candidate = Email(new_email)
    if candidate.value == user.email.value:
        raise ValidationError("That is already your email address.")

    async with uow:
        taken = await uow.users.get_by_email(candidate.value)
        if taken is not None and taken.id != user.id:
            raise ConflictError("That email address is already in use.")

        token = await issue_challenge(
            uow,
            settings,
            user_id=user.id,
            kind=ChallengeKind.EMAIL_CHANGE,
            destination=candidate.value,
            context=context,
        )
        await uow.commit()

    await email_sender.send(
        email_change_email(
            to=candidate.value,
            display_name=user.display_name,
            link=_link(settings, "verify-email-change", token),
        )
    )
    await email_sender.send(
        email_changed_notice(
            to=user.email.value, display_name=user.display_name, new_email=candidate.value
        )
    )


async def verify_email_change(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
    context: RequestContext | None = None,
) -> User:
    """Adopt a confirmed new address and re-verify the account."""
    async with uow:
        challenge = await consume_challenge(
            uow, settings, token=token, kind=ChallengeKind.EMAIL_CHANGE
        )
        user = await uow.users.get(UserId(challenge.user_id))
        if user is None or challenge.destination is None:
            raise ValidationError("This link is not valid or has expired.")

        taken = await uow.users.get_by_email(challenge.destination)
        if taken is not None and taken.id != user.id:
            raise ConflictError("That email address is already in use.")

        user.change_email(Email(challenge.destination))
        user.mark_email_verified()
        await uow.users.update(user)
        await record_event(
            uow, event_type=SecurityEventType.EMAIL_CHANGED, user_id=user.id, context=context
        )
        await uow.commit()
    return user


async def _failed_attempts_recently(uow: UnitOfWork, user_id: UserId) -> int:
    """Failed sign-ins against this account in the recent window.

    A signal, not a risk score: it drives a security event and a notification,
    and deliberately does not consult GeoIP, which belongs to the platform
    security phase.
    """
    since = utcnow() - timedelta(minutes=SUSPICIOUS_WINDOW_MINUTES)
    count = await uow.security_events.count_recent(
        user_id, SecurityEventType.LOGIN_FAILED, since=since
    )
    return count if count >= SUSPICIOUS_ACTIVITY_THRESHOLD else 0


async def _notify_suspicious(
    settings: Settings,
    user: User,
    sender: EmailSender,
    attempts: int,
) -> None:
    try:
        await sender.send(
            security_notice(
                to=user.email.value,
                display_name=user.display_name,
                summary=(
                    f"Someone signed in to your SPA account after {attempts} failed attempts "
                    "in the last few minutes. If this was not you, change your password now."
                ),
            )
        )
    except DeliveryError:
        # The sign-in already succeeded; a notification that could not be sent
        # must not turn a valid session into an error.
        return


def _validate_password(policy: PasswordPolicy, password: str) -> None:
    violations = policy.violations(password)
    if violations:
        raise ValidationError(
            "The password does not meet the requirements.",
            details={"requirements": violations},
        )


def _link(settings: Settings, path: str, token: str) -> str:
    return f"{settings.app_base_url.rstrip('/')}/{path.lstrip('/')}?token={token}"


async def _send_verification(
    settings: Settings,
    user: User,
    token: str,
    *,
    sender: EmailSender | None = None,
) -> None:
    if sender is None:
        raise ConfigurationError("No email sender is configured.")

    try:
        await sender.send(
            verification_email(
                to=user.email.value,
                display_name=user.display_name,
                link=_link(settings, "verify-email", token),
            )
        )
    except DeliveryError as exc:
        raise EmailDeliveryError("The verification email could not be sent.") from exc


__all__ = [
    "RegistrationResult",
    "change_email",
    "login",
    "logout",
    "register_user",
    "resend_verification",
    "verify_email",
    "verify_email_change",
]
