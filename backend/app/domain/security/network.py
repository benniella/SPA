from __future__ import annotations

import ipaddress
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import NewType

from app.domain.shared import UserId, new_id, utcnow

IpBlockId = NewType("IpBlockId", uuid.UUID)

COUNTRY_CODE_LENGTH = 2


class CountryPolicyMode:
    __slots__ = ("value",)

    OFF = "off"
    ALLOWLIST = "allowlist"
    DENYLIST = "denylist"

    ALLOWED = frozenset({OFF, ALLOWLIST, DENYLIST})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown country policy mode: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CountryPolicyMode):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


def normalise_country_code(value: str) -> str:
    code = value.strip().upper()
    if len(code) != COUNTRY_CODE_LENGTH or not code.isalpha() or not code.isascii():
        raise ValueError(f"Country code must be two letters: {value!r}.")
    return code


class IpBlockKind:
    __slots__ = ("value",)

    TEMPORARY = "temporary"
    PERMANENT = "permanent"

    ALLOWED = frozenset({TEMPORARY, PERMANENT})

    def __init__(self, value: str) -> None:
        if value not in self.ALLOWED:
            raise ValueError(f"Unknown IP block kind: {value!r}.")
        self.value = value

    def __str__(self) -> str:
        return self.value

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IpBlockKind):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self.value)


def parse_network(value: str) -> str:
    candidate = value.strip()
    if not candidate:
        raise ValueError("An IP address or network is required.")
    try:
        if "/" in candidate:
            network = ipaddress.ip_network(candidate, strict=False)
        else:
            network = ipaddress.ip_network(ipaddress.ip_address(candidate))
    except ValueError as exc:
        raise ValueError(f"Invalid IP address or network: {value!r}.") from exc
    return str(network)


@dataclass(slots=True)
class IpBlock:
    network: str
    kind: str
    reason: str
    created_by: UserId | None
    id: IpBlockId = field(default_factory=lambda: IpBlockId(new_id()))
    expires_at: datetime | None = None
    removed_at: datetime | None = None
    created_at: datetime = field(default_factory=utcnow)

    def __post_init__(self) -> None:
        self.network = parse_network(self.network)
        IpBlockKind(self.kind)
        self.reason = self.reason.strip()
        if not self.reason:
            raise ValueError("A reason is required for an IP block.")
        if self.kind == IpBlockKind.TEMPORARY and self.expires_at is None:
            raise ValueError("A temporary block requires an expiry.")
        if self.kind == IpBlockKind.PERMANENT:
            self.expires_at = None

    @property
    def is_removed(self) -> bool:
        return self.removed_at is not None

    def is_expired(self, *, at: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        return (at or utcnow()) >= self.expires_at

    def is_active(self, *, at: datetime | None = None) -> bool:
        return not self.is_removed and not self.is_expired(at=at)

    def remove(self, *, at: datetime | None = None) -> None:
        if self.removed_at is None:
            self.removed_at = at or utcnow()

    def covers(self, address: str) -> bool:
        try:
            network = ipaddress.ip_network(self.network)
            candidate = ipaddress.ip_address(address.strip())
        except ValueError:
            return False
        return candidate.version == network.version and candidate in network


def temporary_expiry(minutes: int, *, at: datetime | None = None) -> datetime:
    return (at or utcnow()) + timedelta(minutes=minutes)
