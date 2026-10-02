"""Verified phone numbers.

A phone number is only recorded as the account's verified contact once a code
sent to it has been returned. Until then it is a pending challenge, which is what
makes it usable as a recovery channel.
"""

from __future__ import annotations

from app.application.ports.notifications import DeliveryError, SmsMessage, SmsSender
from app.application.ports.security import RateLimiter
from app.application.ports.unit_of_work import UnitOfWork
from app.application.security import (
    RequestContext,
    issue_otp,
    record_event,
    verify_otp,
)
from app.application.use_cases.authentication import _enforce, _rate_key
from app.core.config import Settings
from app.core.errors import ConfigurationError, EmailDeliveryError
from app.domain.security.entities import OtpPurpose, SecurityEventType
from app.domain.users.credentials import normalise_phone
from app.domain.users.entities import User


def _require_delivery(sender: SmsSender) -> None:
    if not getattr(sender, "configured", False):
        # Refusing is the honest outcome: issuing a code nothing can deliver
        # would leave the user waiting for an SMS and the account unchanged.
        raise ConfigurationError("No SMS provider is configured for this deployment.")


async def request_phone_verification(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user: User,
    phone_number: str,
    sms_sender: SmsSender,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> None:
    _require_delivery(sms_sender)
    await _enforce(
        limiter,
        _rate_key("phone-request", client_key),
        limit=settings.rate_limit_phone_per_hour,
        window_seconds=3600,
    )

    normalised = normalise_phone(phone_number)
    if len(normalised) < 8:
        from app.core.errors import ValidationError

        raise ValidationError("Enter a phone number including its country code.")

    async with uow:
        code = await issue_otp(
            uow,
            settings,
            user_id=user.id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            destination=normalised,
            context=context,
        )
        await uow.commit()

    try:
        await sms_sender.send(
            SmsMessage(to=normalised, body=f"Your SPA verification code is {code}.")
        )
    except DeliveryError as exc:
        raise EmailDeliveryError("The verification code could not be sent.") from exc


async def verify_phone(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user: User,
    code: str,
    limiter: RateLimiter,
    client_key: str,
    context: RequestContext | None = None,
) -> User:
    await _enforce(
        limiter,
        _rate_key("phone-verify", client_key),
        limit=settings.rate_limit_phone_per_hour,
        window_seconds=3600,
    )

    async with uow:
        challenge = await verify_otp(
            uow,
            settings,
            user_id=user.id,
            purpose=OtpPurpose.PHONE_VERIFICATION,
            code=code,
        )
        stored = await uow.users.get(user.id)
        if stored is None:
            raise ConfigurationError("The account could not be loaded.")
        stored.mark_phone_verified(challenge.destination)
        await uow.users.update(stored)
        await record_event(
            uow,
            event_type=SecurityEventType.PHONE_VERIFIED,
            user_id=stored.id,
            context=context,
        )
        await uow.commit()
    return stored


async def remove_phone(
    uow: UnitOfWork,
    *,
    user: User,
    context: RequestContext | None = None,
) -> User:
    """Remove the verified number.

    No code is required: dropping a recovery channel reduces access rather than
    granting it, and demanding an SMS to stop using SMS would strand a user whose
    number changed.
    """
    async with uow:
        stored = await uow.users.get(user.id)
        if stored is None:
            raise ConfigurationError("The account could not be loaded.")
        stored.remove_phone_number()
        await uow.users.update(stored)
        await record_event(
            uow,
            event_type=SecurityEventType.PHONE_REMOVED,
            user_id=stored.id,
            context=context,
        )
        await uow.commit()
    return stored
