"""In-memory fakes for the account-security ports.

Kept beside the other application-layer fakes so a use-case test can exercise
sessions, challenges, OTP and the security log without a database.
"""

from __future__ import annotations

from app.application.ports.notifications import EmailMessage, SmsMessage
from app.application.ports.security import RateLimitDecision
from app.domain.security.entities import (
    Challenge,
    OtpChallenge,
    SecurityEvent,
    Session,
)
from app.domain.shared import UserId


class FakeSessionRepository:
    def __init__(self) -> None:
        self._by_id: dict[object, Session] = {}
        self._token_hashes: dict[object, str] = {}

    async def add(self, session: Session, *, token_hash: str) -> None:
        self._by_id[session.id] = session
        self._token_hashes[session.id] = token_hash

    async def get_by_token_hash(self, token_hash: str) -> Session | None:
        for session_id, stored in self._token_hashes.items():
            if stored == token_hash:
                return self._by_id[session_id]
        return None

    async def get_for_user(self, session_id: object, user_id: UserId) -> Session | None:
        session = self._by_id.get(session_id)
        if session is None or session.user_id != user_id:
            return None
        return session

    async def list_for_user(self, user_id: UserId) -> list[Session]:
        return [s for s in self._by_id.values() if s.user_id == user_id]

    async def update(self, session: Session) -> None:
        self._by_id[session.id] = session

    async def revoke_all_for_user(self, user_id: UserId, *, except_session_id: object = None) -> int:
        revoked = 0
        for session in self._by_id.values():
            if session.user_id != user_id or session.is_revoked:
                continue
            if except_session_id is not None and str(session.id) == str(except_session_id):
                continue
            session.revoke()
            revoked += 1
        return revoked


class FakeChallengeRepository:
    def __init__(self) -> None:
        self._challenges: list[Challenge] = []

    async def add(self, challenge: Challenge) -> None:
        self._challenges.append(challenge)

    async def get_by_token_hash(self, token_hash: str) -> Challenge | None:
        for challenge in self._challenges:
            if challenge.token_hash == token_hash:
                return challenge
        return None

    async def consume(self, challenge: Challenge) -> None:
        challenge.consume()

    async def invalidate_active(self, user_id: UserId, kind: str) -> int:
        invalidated = 0
        for challenge in self._challenges:
            if challenge.user_id == user_id and challenge.kind == kind and challenge.is_usable():
                challenge.consume()
                invalidated += 1
        return invalidated

    async def latest_for_user(self, user_id: UserId, kind: str) -> Challenge | None:
        matching = [
            c for c in self._challenges if c.user_id == user_id and c.kind == kind
        ]
        return matching[-1] if matching else None


class FakeOtpChallengeRepository:
    def __init__(self) -> None:
        self._challenges: list[OtpChallenge] = []

    async def add(self, challenge: OtpChallenge) -> None:
        self._challenges.append(challenge)

    async def latest_for_user(self, user_id: UserId, purpose: str) -> OtpChallenge | None:
        matching = [
            c for c in self._challenges if c.user_id == user_id and c.purpose == purpose
        ]
        return matching[-1] if matching else None

    async def update(self, challenge: OtpChallenge) -> None:
        return None

    async def invalidate_active(self, user_id: UserId, purpose: str) -> int:
        invalidated = 0
        for challenge in self._challenges:
            if challenge.user_id == user_id and challenge.purpose == purpose and challenge.is_usable():
                challenge.consume()
                invalidated += 1
        return invalidated


class FakeSecurityEventRepository:
    """Append and read only, mirroring the port's lack of update and delete."""

    def __init__(self) -> None:
        self.events: list[SecurityEvent] = []

    async def add(self, event: SecurityEvent) -> None:
        self.events.append(event)

    async def list_for_user(
        self,
        user_id: UserId,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[SecurityEvent]:
        matching = [
            event
            for event in self.events
            if event.user_id == user_id and (event_type is None or event.event_type == event_type)
        ]
        matching.sort(key=lambda event: event.created_at, reverse=True)
        return matching[offset : offset + limit]

    async def list_administrative(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        event_type: str | None = None,
    ) -> list[SecurityEvent]:
        matching = [
            event
            for event in self.events
            if str(event.event_type).startswith("ADMIN_")
            and (event_type is None or event.event_type == event_type)
        ]
        matching.sort(key=lambda event: event.created_at, reverse=True)
        return matching[offset : offset + limit]

    async def count_recent(self, user_id: UserId | None, event_type: str, *, since: object) -> int:
        return sum(
            1
            for event in self.events
            if event.user_id == user_id
            and event.event_type == event_type
            and event.created_at >= since  # type: ignore[operator]
        )


class FakePasswordHasher:
    """A deterministic hasher: fast, and it never stores the plaintext."""

    prefix = "fake$"

    def hash(self, password: str) -> str:
        return f"{self.prefix}{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"{self.prefix}{password}"

    def needs_rehash(self, password_hash: str) -> bool:
        return not password_hash.startswith(self.prefix)


class FakeRateLimiter:
    """A counter store that never fails open for a test that wants a limit hit."""

    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.reset_calls: list[str] = []

    async def hit(self, key: str, *, limit: int, window_seconds: int) -> RateLimitDecision:
        self.counts[key] = self.counts.get(key, 0) + 1
        count = self.counts[key]
        allowed = count <= limit
        return RateLimitDecision(
            allowed=allowed,
            remaining=max(0, limit - count),
            retry_after_seconds=0 if allowed else window_seconds,
        )

    async def peek(self, key: str) -> int | None:
        return self.counts.get(key)

    async def reset(self, key: str) -> None:
        self.reset_calls.append(key)
        self.counts.pop(key, None)


class RecordingEmailSender:
    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


class RecordingSmsSender:
    def __init__(self, *, configured: bool = True) -> None:
        self.messages: list[SmsMessage] = []
        self._configured = configured

    @property
    def configured(self) -> bool:
        return self._configured

    async def send(self, message: SmsMessage) -> None:
        self.messages.append(message)


def token_from(message: EmailMessage) -> str:
    """The challenge token carried by a delivered link."""
    _, _, tail = message.text.rpartition("token=")
    return tail.split()[0].strip()


__all__ = [
    "FakeChallengeRepository",
    "FakeOtpChallengeRepository",
    "FakePasswordHasher",
    "FakeRateLimiter",
    "FakeSecurityEventRepository",
    "FakeSessionRepository",
    "RecordingEmailSender",
    "RecordingSmsSender",
    "token_from",
]
