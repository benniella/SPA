"""Persistence ports for platform configuration and network security controls."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.security.network import IpBlock


@runtime_checkable
class PlatformSettingRepository(Protocol):
    async def get(self, key: str) -> object | None:
        """The stored value for a key, or None when it has never been set."""

    async def list(self) -> dict[str, object]:
        """Every stored setting, keyed by name."""

    async def set(
        self,
        key: str,
        value: object,
        *,
        changed_by: object | None,
    ) -> None:
        """Store a value, recording who changed it."""

    async def delete(self, key: str) -> None:
        """Remove a stored value so the default applies again."""


@runtime_checkable
class IpBlockRepository(Protocol):
    async def add(self, block: IpBlock) -> None: ...

    async def get(self, block_id: object) -> IpBlock | None: ...

    async def list_active(self) -> list[IpBlock]:
        """Blocks that are neither removed nor expired."""

    async def list_all(self) -> list[IpBlock]:
        """Every block, newest first, for the administrative list."""

    async def update(self, block: IpBlock) -> None:
        """Persist a removal."""


__all__ = ["IpBlockRepository", "PlatformSettingRepository"]
