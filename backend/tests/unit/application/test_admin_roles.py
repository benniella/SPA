"""Administrative role assignment and the privilege-escalation boundary."""

from __future__ import annotations

import pytest

from app.application.admin_authz import MissingPrivilege, build_context
from app.application.use_cases.admin_roles import (
    list_administrator_roles,
    set_administrator_roles,
)
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.admin.entities import AdminIdentity, AdminPrivilege, AdminRole, AdminStatus
from app.domain.security.entities import SecurityEventType
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

    async def superadmin_context(self):
        return await self.context_for(await self.add_admin(roles=(AdminRole.SUPERADMIN,)))


@pytest.fixture
def harness() -> Harness:
    return Harness()


async def _set(harness: Harness, actor, target, names: list[str]):
    return await set_administrator_roles(
        actor,
        target.id,
        names,
        admins=harness.admins,
        roles=harness.roles,
        security_events=harness.events,
    )


class TestAssignment:
    async def test_a_superadmin_can_assign_a_role(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin()

        result = await _set(harness, actor, target, [AdminRole.SUPPORT_ADMIN])

        assert result == [AdminRole.SUPPORT_ADMIN]
        assert any(
            e.event_type == SecurityEventType.ADMIN_ROLE_ASSIGNED for e in harness.events.events
        )

    async def test_assigning_the_same_role_twice_is_a_no_op(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))

        result = await _set(harness, actor, target, [AdminRole.SUPPORT_ADMIN])

        assert result == [AdminRole.SUPPORT_ADMIN]

    async def test_removing_a_role_takes_its_privileges_away(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin(roles=(AdminRole.SECURITY_ADMIN,))
        target_context = await harness.context_for(target)
        assert target_context.holds(AdminPrivilege.SECURITY_MANAGE)

        await _set(harness, actor, target, [])

        refreshed = await harness.context_for(target)
        assert not refreshed.holds(AdminPrivilege.SECURITY_MANAGE)
        assert any(
            e.event_type == SecurityEventType.ADMIN_ROLE_REMOVED for e in harness.events.events
        )

    async def test_an_unknown_role_is_a_validation_error(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin()
        with pytest.raises(ValidationError):
            await _set(harness, actor, target, ["not_a_role"])

    async def test_an_unknown_administrator_is_a_not_found(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        with pytest.raises(NotFoundError):
            await set_administrator_roles(
                actor,
                new_id(),
                [],
                admins=harness.admins,
                roles=harness.roles,
                security_events=harness.events,
            )


class TestEscalation:
    async def test_an_admin_cannot_grant_a_role_it_does_not_itself_hold(
        self, harness: Harness
    ) -> None:
        actor_admin = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        target = await harness.add_admin()

        with pytest.raises(ConflictError):
            await _set(harness, actor, target, [AdminRole.FINANCE_ADMIN])

    async def test_an_admin_cannot_escalate_itself(self, harness: Harness) -> None:
        actor_admin = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)

        with pytest.raises(ConflictError):
            await _set(harness, actor, actor_admin, [AdminRole.SECURITY_ADMIN])

    async def test_only_a_superadmin_may_grant_superadmin(self, harness: Harness) -> None:
        actor_admin = await harness.add_admin(roles=(AdminRole.OPERATIONS_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        target = await harness.add_admin()

        with pytest.raises(ConflictError):
            await _set(harness, actor, target, [AdminRole.SUPERADMIN])

    async def test_an_admin_cannot_manage_a_superadmin(self, harness: Harness) -> None:
        actor_admin = await harness.add_admin(roles=(AdminRole.OPERATIONS_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        superadmin = await harness.add_admin(roles=(AdminRole.SUPERADMIN,))

        with pytest.raises(ConflictError):
            await _set(harness, actor, superadmin, [])

    async def test_an_admin_without_the_manage_privilege_is_refused(
        self, harness: Harness
    ) -> None:
        actor = await harness.context_for(
            await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        )
        target = await harness.add_admin()
        with pytest.raises(MissingPrivilege):
            await _set(harness, actor, target, [AdminRole.SUPPORT_ADMIN])

    async def test_a_superadmin_may_grant_superadmin(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin()

        result = await _set(harness, actor, target, [AdminRole.SUPERADMIN])

        assert result == [AdminRole.SUPERADMIN]
        promoted = await harness.context_for(target)
        assert promoted.is_superadmin


class TestListing:
    async def test_roles_are_listed_for_an_administrator(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        target = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))

        listed = await list_administrator_roles(
            actor, target.id, admins=harness.admins, roles=harness.roles
        )

        assert listed == [AdminRole.SUPPORT_ADMIN]

    async def test_listing_roles_requires_the_read_privilege(self, harness: Harness) -> None:
        actor = await harness.context_for(await harness.add_admin())
        target = await harness.add_admin()
        with pytest.raises(MissingPrivilege):
            await list_administrator_roles(
                actor, target.id, admins=harness.admins, roles=harness.roles
            )
