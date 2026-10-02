"""Administrative audit retrieval."""

from __future__ import annotations

import pytest

from app.application.admin_authz import MissingPrivilege, build_context
from app.application.use_cases.admin_administrators import suspend_administrator
from app.application.use_cases.admin_audit import list_administrative_events
from app.domain.admin.entities import AdminIdentity, AdminRole, AdminStatus
from app.domain.security.entities import SecurityEvent, SecurityEventType
from app.domain.shared import UserId, new_id, utcnow
from tests.unit.application.fakes import (
    FakeAdminPrivilegeRepository,
    FakeAdminRepository,
    FakeAdminRoleRepository,
)
from tests.unit.application.security_fakes import FakeSecurityEventRepository


class Harness:
    def __init__(self) -> None:
        self.admins = FakeAdminRepository()
        self.roles = FakeAdminRoleRepository()
        self.privileges = FakeAdminPrivilegeRepository()
        self.events = FakeSecurityEventRepository()

    async def add_admin(self, *, roles: tuple[str, ...] = ()) -> AdminIdentity:
        admin = AdminIdentity(
            user_id=UserId(new_id()),
            status=AdminStatus(AdminStatus.ACTIVE),
            mfa_enrolled_at=utcnow(),
        )
        await self.admins.add(admin)
        for name in roles:
            await self.roles.assign(admin.id, AdminRole(name), assigned_by=None)
        return admin

    async def context_for(self, admin: AdminIdentity):
        return await build_context(
            admin.user_id,
            admins=self.admins,
            roles=self.roles,
            privileges=self.privileges,
            mfa_satisfied=True,
        )


@pytest.fixture
def harness() -> Harness:
    return Harness()


class TestAuditRead:
    async def test_reading_requires_the_security_read_privilege(self, harness: Harness) -> None:
        actor = await harness.context_for(
            await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        )
        with pytest.raises(MissingPrivilege):
            await list_administrative_events(actor, security_events=harness.events)

    async def test_a_security_admin_can_read_administrative_events(
        self, harness: Harness
    ) -> None:
        actor_admin = await harness.add_admin(roles=(AdminRole.SECURITY_ADMIN,))
        actor = await harness.context_for(actor_admin)
        superadmin = await harness.context_for(
            await harness.add_admin(roles=(AdminRole.SUPERADMIN,))
        )
        target = await harness.add_admin()
        await suspend_administrator(
            superadmin,
            target.id,
            admins=harness.admins,
            roles=harness.roles,
            privileges=harness.privileges,
            security_events=harness.events,
        )

        listed = await list_administrative_events(actor, security_events=harness.events)

        assert [str(e.event_type) for e in listed] == [SecurityEventType.ADMIN_SUSPENDED]

    async def test_non_administrative_events_are_not_listed(self, harness: Harness) -> None:
        actor = await harness.context_for(await harness.add_admin(roles=(AdminRole.SUPERADMIN,)))
        await harness.events.add(
            SecurityEvent(
                user_id=UserId(new_id()),
                event_type=str(SecurityEventType.LOGIN_SUCCESS),
            )
        )
        await harness.events.add(
            SecurityEvent(
                user_id=UserId(new_id()),
                event_type=str(SecurityEventType.ADMIN_REVOKED),
            )
        )

        listed = await list_administrative_events(actor, security_events=harness.events)

        assert [str(e.event_type) for e in listed] == [SecurityEventType.ADMIN_REVOKED]

    async def test_listing_is_paginated_in_stable_order(self, harness: Harness) -> None:
        actor = await harness.context_for(await harness.add_admin(roles=(AdminRole.SUPERADMIN,)))
        for _index in range(5):
            await harness.events.add(
                SecurityEvent(
                    user_id=UserId(new_id()),
                    event_type=str(SecurityEventType.ADMIN_REVOKED),
                )
            )

        first = await list_administrative_events(
            actor, security_events=harness.events, limit=2, offset=0
        )
        second = await list_administrative_events(
            actor, security_events=harness.events, limit=2, offset=2
        )

        assert len(first) == 2
        assert len(second) == 2
        assert {id(event) for event in first}.isdisjoint({id(event) for event in second})

    async def test_events_can_be_filtered_by_type(self, harness: Harness) -> None:
        actor = await harness.context_for(await harness.add_admin(roles=(AdminRole.SUPERADMIN,)))
        await harness.events.add(
            SecurityEvent(user_id=None, event_type=str(SecurityEventType.ADMIN_REVOKED))
        )
        await harness.events.add(
            SecurityEvent(user_id=None, event_type=str(SecurityEventType.ADMIN_SUSPENDED))
        )

        listed = await list_administrative_events(
            actor,
            security_events=harness.events,
            event_type=SecurityEventType.ADMIN_SUSPENDED,
        )

        assert [str(e.event_type) for e in listed] == [SecurityEventType.ADMIN_SUSPENDED]
