"""Password reset, password change and account recovery."""

from __future__ import annotations

from app.application.messages import password_reset_email, security_notice
from app.application.ports.notifications import EmailSender, SmsSender
from app.application.ports.security import RateLimiter
from app.application.ports.unit_of_work import UnitOfWork
from app.application.security import (
    RequestContext,
    consume_challenge,
    issue_challenge,
    issue_otp,
    record_event,
    verify_otp,
)
from app.application.sessions import revoke_all_sessions
from app.application.use_cases.authentication import _enforce, _link, _rate_key, _validate_password
from app.core.config import Settings
from app.core.errors import (
    AuthenticationError,
    ConfigurationError,
    EmailDeliveryError,
    InvalidStateError,
    RateLimitedError,
    ValidationError,
)
from app.domain.security.entities import (
    ChallengeKind,
    OtpPurpose,
    SecurityEventType,
)
from app.domain.shared import UserId
from app.domain.users.credentials import PasswordHasher, PasswordPolicy
from app.domain.users.entities import User


async def request_password_reset(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    email_sender: EmailSender,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> None:
    """Send a reset link to a known, usable account.

    The response is identical for an unknown address, a usable account and an
    account that may not authenticate, because revealing which addresses are
    registered is the whole value of probing this endpoint.
    """
    await _enforce(
        limiter,
        _rate_key("forgot-password", client_key),
        limit=settings.rate_limit_password_reset_per_hour,
        window_seconds=3600,
    )

    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None or not user.has_password:
            return
        token = await issue_challenge(
            uow,
            settings,
            user_id=user.id,
            kind=ChallengeKind.PASSWORD_RESET,
            destination=user.email.value,
            context=context,
        )
        await uow.commit()

    try:
        await email_sender.send(
            password_reset_email(
                to=user.email.value,
                display_name=user.display_name,
                link=_link(settings, "reset-password", token),
            )
        )
    except Exception:
        # The account state is unchanged, so an undeliverable reset is not a
        # request failure the user must retry through a different path; it is an
        # operational problem, surfaced to the caller as a delivery failure.
        raise


async def reset_password(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
    new_password: str,
    hasher: PasswordHasher,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> User:
    """Set a new password from a reset challenge and end every existing session."""
    await _enforce(
        limiter,
        _rate_key("reset-password", client_key),
        limit=settings.rate_limit_password_reset_per_hour,
        window_seconds=3600,
    )

    policy = PasswordPolicy(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
    )
    _validate_password(policy, new_password)

    async with uow:
        challenge = await consume_challenge(
            uow, settings, token=token, kind=ChallengeKind.PASSWORD_RESET
        )
        user = await uow.users.get(UserId(challenge.user_id))
        if user is None:
            raise ValidationError("This link is not valid or has expired.")

        user.set_password_hash(hasher.hash(new_password))
        user.mark_email_verified()
        await uow.users.update(user)
        revoked = await revoke_all_sessions(uow, user_id=user.id, context=context)
        await record_event(
            uow,
            event_type=SecurityEventType.PASSWORD_RESET_COMPLETED,
            user_id=user.id,
            context=context,
            metadata={"sessions_revoked": revoked},
        )
        await uow.commit()

    await _notify(settings, user, "Your SPA password was reset.", email_sender=None)
    return user


async def change_password(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user: User,
    current_password: str,
    new_password: str,
    hasher: PasswordHasher,
    keep_session_id: object = None,
    email_sender: EmailSender | None = None,
    context: RequestContext | None = None,
) -> int:
    """Change a password, proving the current one.

    Every other session is revoked. A password change is the action a user takes
    when they believe they are compromised, and leaving the other sessions alive
    would make that belief false.
    """
    if not user.has_password:
        raise InvalidStateError("This account has no password to change.")
    if not hasher.verify(current_password, user.password_hash or ""):
        raise AuthenticationError("The current password is not correct.")

    policy = PasswordPolicy(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
    )
    _validate_password(policy, new_password)
    if new_password == current_password:
        raise ValidationError("Choose a password you have not used here before.")

    async with uow:
        user.set_password_hash(hasher.hash(new_password))
        await uow.users.update(user)
        revoked = await revoke_all_sessions(
            uow, user_id=user.id, except_session_id=keep_session_id, context=context
        )
        await record_event(
            uow,
            event_type=SecurityEventType.PASSWORD_CHANGED,
            user_id=user.id,
            context=context,
            metadata={"sessions_revoked": revoked},
        )
        await uow.commit()

    if email_sender is not None:
        await _notify(
            settings,
            user,
            "Your SPA password was changed. If this was not you, reset it now.",
            email_sender=email_sender,
        )
    return revoked


async def start_recovery(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> bool:
    """Begin account recovery for an address with a verified phone number.

    Returns whether a code was issued, so the API can answer identically either
    way. Recovery uses a verified contact method as its second factor; it does not
    add a way to bypass the checks that sign-in and reset already impose, and
    there is deliberately no operator override.
    """
    await _enforce(
        limiter,
        _rate_key("recovery", client_key),
        limit=settings.rate_limit_password_reset_per_hour,
        window_seconds=3600,
    )

    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None or not user.is_phone_verified or user.phone_number is None:
            return False
        code = await issue_otp(
            uow,
            settings,
            user_id=user.id,
            purpose=OtpPurpose.ACCOUNT_RECOVERY,
            destination=user.phone_number,
            context=context,
        )
        await uow.commit()

    from app.application.ports.notifications import SmsMessage

    sms: SmsSender = _sms_sender(settings)
    if not getattr(sms, "configured", False):
        raise ConfigurationError("No SMS provider is configured.")
    await sms.send(SmsMessage(to=user.phone_number, body=f"Your SPA recovery code is {code}."))
    return True


async def complete_recovery(
    uow: UnitOfWork,
    settings: Settings,
    *,
    email: str,
    code: str,
    new_password: str,
    hasher: PasswordHasher,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> User:
    """Finish recovery: verify the code, set a new password, end all sessions."""
    await _enforce(
        limiter,
        _rate_key("recovery-complete", client_key),
        limit=settings.rate_limit_password_reset_per_hour,
        window_seconds=3600,
    )

    policy = PasswordPolicy(
        min_length=settings.password_min_length,
        max_length=settings.password_max_length,
    )
    _validate_password(policy, new_password)

    async with uow:
        user = await uow.users.get_by_email(email)
        if user is None:
            # The same failure as a wrong code: recovery must not confirm whether
            # an address has a recoverable account.
            raise ValidationError("That code is not correct.")

        await verify_otp(
            uow,
            settings,
            user_id=user.id,
            purpose=OtpPurpose.ACCOUNT_RECOVERY,
            code=code,
        )
        user.set_password_hash(hasher.hash(new_password))
        if user.account_status.value == "suspended":
            raise InvalidStateError("This account cannot be recovered right now.")
        user.mark_email_verified()
        await uow.users.update(user)
        revoked = await revoke_all_sessions(uow, user_id=user.id, context=context)
        await record_event(
            uow,
            event_type=SecurityEventType.RECOVERY_COMPLETED,
            user_id=user.id,
            context=context,
            metadata={"sessions_revoked": revoked},
        )
        await uow.commit()
    return user


def _sms_sender(settings: Settings) -> SmsSender:
    from app.core.errors import ConfigurationError as _ConfigurationError
    from app.infrastructure.notifications.factory import build_sms_sender

    try:
        return build_sms_sender(settings)
    except Exception as exc:  # pragma: no cover - defensive
        raise _ConfigurationError("No SMS provider is configured.") from exc


async def _notify(
    settings: Settings,
    user: User,
    summary: str,
    *,
    email_sender: EmailSender | None,
) -> None:
    if email_sender is None:
        return
    try:
        await email_sender.send(
            security_notice(to=user.email.value, display_name=user.display_name, summary=summary)
        )
    except Exception:
        # A notification that failed to send must not roll back a completed
        # password change; the state change is the fact and the mail is advisory.
        return


__all__ = [
    "EmailDeliveryError",
    "RateLimitedError",
    "change_password",
    "complete_recovery",
    "request_password_reset",
    "reset_password",
    "start_recovery",
]
