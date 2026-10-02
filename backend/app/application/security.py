"""Account-security services shared by the authentication use cases.

Challenges and OTP codes are stored as keyed hashes, created through a single
place so the expiry, the invalidation of a previous challenge and the security
event that accompanies them cannot be applied inconsistently.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from app.application.ports.notifications import SmsSender
from app.application.ports.unit_of_work import UnitOfWork
from app.core.config import Settings
from app.core.errors import InvalidStateError, RateLimitedError, ValidationError
from app.domain.security.entities import (
    Challenge,
    ChallengeKind,
    OtpChallenge,
    OtpPurpose,
    SecurityEvent,
    SecurityEventType,
    expiry_from,
)
from app.domain.security.tokens import (
    generate_otp,
    generate_token,
    hash_otp,
    hash_token,
    tokens_match,
)
from app.domain.shared import UserId, utcnow

TOKEN_TTL_ATTRIBUTE = {
    ChallengeKind.EMAIL_VERIFICATION: "email_verification_ttl_hours",
    ChallengeKind.EMAIL_CHANGE: "email_change_ttl_hours",
    ChallengeKind.PASSWORD_RESET: "password_reset_ttl_hours",
    ChallengeKind.RECOVERY: "recovery_ttl_hours",
}

CHALLENGE_EVENT = {
    ChallengeKind.EMAIL_VERIFICATION: SecurityEventType.EMAIL_VERIFICATION_REQUESTED,
    ChallengeKind.EMAIL_CHANGE: SecurityEventType.EMAIL_CHANGE_REQUESTED,
    ChallengeKind.PASSWORD_RESET: SecurityEventType.PASSWORD_RESET_REQUESTED,
    ChallengeKind.RECOVERY: SecurityEventType.RECOVERY_STARTED,
}

OTP_EVENT = {
    OtpPurpose.PHONE_VERIFICATION: SecurityEventType.PHONE_VERIFICATION_REQUESTED,
    OtpPurpose.PHONE_REMOVAL: SecurityEventType.PHONE_VERIFICATION_REQUESTED,
    OtpPurpose.EMAIL_VERIFICATION: SecurityEventType.EMAIL_VERIFICATION_REQUESTED,
    OtpPurpose.ACCOUNT_RECOVERY: SecurityEventType.RECOVERY_STARTED,
    OtpPurpose.SENSITIVE_ACTION: SecurityEventType.SUSPICIOUS_ACTIVITY,
}


@dataclass(frozen=True, slots=True)
class RequestContext:
    """Everything the security log records about who made a request.

    'ip_prefix' is truncated before it reaches here; the full address is personal
    data that a security log does not need, and the network is what is useful
    when investigating.
    """

    ip_prefix: str | None = None
    user_agent: str | None = None


def request_context(
    *,
    client_host: str | None,
    user_agent: str | None,
    ipv6_prefix: int = 64,
    ipv4_prefix: int = 24,
) -> RequestContext:
    """Derive a safe context from a request.

    The address is reduced to its network prefix so that the stored value
    identifies a network rather than a person, while still being the right
    granularity to spot a change of origin.
    """
    return RequestContext(
        ip_prefix=_truncate_address(client_host, ipv6_prefix=ipv6_prefix, ipv4_prefix=ipv4_prefix),
        user_agent=(user_agent or None) and user_agent[:300],
    )


def _truncate_address(address: str | None, *, ipv6_prefix: int, ipv4_prefix: int) -> str | None:
    if not address:
        return None
    if ":" in address:
        groups = address.split(":")
        keep = max(1, ipv6_prefix // 16)
        return ":".join(groups[:keep]) + "::"
    octets = address.split(".")
    if len(octets) != 4:
        return None
    keep = max(1, ipv4_prefix // 8)
    return ".".join(octets[:keep]) + ".0" * (4 - keep)


async def record_event(
    uow: UnitOfWork,
    *,
    event_type: str,
    user_id: UserId | None,
    context: RequestContext | None = None,
    metadata: dict[str, object] | None = None,
) -> None:
    """Append a security event. Never raises and never carries secret material."""
    await uow.security_events.add(
        SecurityEvent(
            user_id=user_id,
            event_type=event_type,
            ip_prefix=context.ip_prefix if context else None,
            user_agent=context.user_agent if context else None,
            metadata=metadata or {},
        )
    )


def policy_for(settings: Settings, kind: str) -> int:
    return int(getattr(settings, TOKEN_TTL_ATTRIBUTE[kind]))


async def issue_challenge(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user_id: UserId,
    kind: str,
    destination: str | None = None,
    context: RequestContext | None = None,
    enforce_cooldown: bool = True,
) -> str:
    """Create a single-use challenge and return its raw token.

    The raw token is returned to the caller for delivery and is never persisted,
    logged or returned through the API. Any outstanding challenge of the same kind
    is consumed first, so a resend does not leave a trail of live links.
    """
    if enforce_cooldown:
        await enforce_resend_cooldown(uow, settings, user_id=user_id, kind=kind)

    token = generate_token()
    challenge = Challenge(
        user_id=user_id,
        kind=kind,
        token_hash=hash_token(token, secret=settings.session_secret),
        expires_at=expiry_from(timedelta(hours=policy_for(settings, kind))),
        destination=destination,
    )
    await uow.challenges.invalidate_active(user_id, kind)
    await uow.challenges.add(challenge)
    await record_event(
        uow, event_type=CHALLENGE_EVENT[kind], user_id=user_id, context=context
    )
    return token


async def consume_challenge(
    uow: UnitOfWork,
    settings: Settings,
    *,
    token: str,
    kind: str,
) -> Challenge:
    """Resolve a raw token to its challenge and burn it.

    A missing, expired, already-used or wrong-purpose token is the same failure:
    telling a caller which of those applies would confirm whether a token ever
    existed.
    """
    challenge = await uow.challenges.get_by_token_hash(
        hash_token(token, secret=settings.session_secret)
    )
    if challenge is None or challenge.kind != kind or not challenge.is_usable():
        raise ValidationError("This link is not valid or has expired.")
    challenge.consume()
    await uow.challenges.consume(challenge)
    return challenge


async def enforce_resend_cooldown(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user_id: UserId,
    kind: str,
) -> None:
    latest = await uow.challenges.latest_for_user(user_id, kind)
    if latest is None:
        return
    elapsed = (utcnow() - latest.created_at).total_seconds()
    remaining = settings.otp_resend_cooldown_seconds - elapsed
    if remaining > 0:
        raise RateLimitedError(
            "Wait before requesting another message.",
            retry_after_seconds=int(remaining) + 1,
        )


async def issue_otp(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user_id: UserId,
    purpose: str,
    destination: str,
    context: RequestContext | None = None,
) -> str:
    """Create a one-time code and return it for delivery.

    Only the code's hash is persisted. The plaintext code exists in memory for
    the duration of the call and in the delivered message; it is never logged.
    """
    latest = await uow.otp_challenges.latest_for_user(user_id, purpose)
    if latest is not None:
        elapsed = (utcnow() - latest.created_at).total_seconds()
        remaining = settings.otp_resend_cooldown_seconds - elapsed
        if remaining > 0:
            raise RateLimitedError(
                "Wait before requesting another code.",
                retry_after_seconds=int(remaining) + 1,
            )

    code = generate_otp(digits=settings.otp_length)
    challenge = OtpChallenge(
        user_id=user_id,
        purpose=purpose,
        code_hash=hash_otp(code, secret=settings.session_secret),
        destination=destination,
        expires_at=expiry_from(timedelta(minutes=settings.otp_ttl_minutes)),
        max_attempts=settings.otp_max_attempts,
    )
    await uow.otp_challenges.invalidate_active(user_id, purpose)
    await uow.otp_challenges.add(challenge)
    await record_event(
        uow, event_type=OTP_EVENT[purpose], user_id=user_id, context=context
    )
    return code


async def verify_otp(
    uow: UnitOfWork,
    settings: Settings,
    *,
    user_id: UserId,
    purpose: str,
    code: str,
) -> OtpChallenge:
    """Check a submitted code, counting the attempt whether or not it matches.

    The attempt is persisted before the comparison so that an attacker cannot
    keep guessing by crashing or abandoning the request, and the reply does not
    say how many attempts remain.
    """
    challenge = await uow.otp_challenges.latest_for_user(user_id, purpose)
    if challenge is None or challenge.is_expired():
        raise InvalidStateError("Request a new verification code.")
    if challenge.is_consumed:
        raise InvalidStateError("This code has already been used.")
    if challenge.attempts_exhausted:
        raise RateLimitedError("Too many incorrect attempts. Request a new code.")

    challenge.register_attempt()
    await uow.otp_challenges.update(challenge)

    if not tokens_match(challenge.code_hash, hash_otp(code, secret=settings.session_secret)):
        if challenge.attempts_exhausted:
            raise RateLimitedError("Too many incorrect attempts. Request a new code.")
        raise ValidationError("That code is not correct.")

    challenge.consume()
    await uow.otp_challenges.update(challenge)
    return challenge


def sender_is_configured(sender: SmsSender) -> bool:
    return bool(getattr(sender, "configured", False))
