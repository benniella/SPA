"""Administrator read and lifecycle use cases."""

from __future__ import annotations

import pytest

from app.application.admin_authz import (
    AdminContext,
    AdministratorMayNotAct,
    MissingPrivilege,
    build_context,
)
from app.application.use_cases.admin_administrators import (
    get_administrator,
    list_administrators,
    list_privileges,
    list_roles,
    reactivate_administrator,
    require_not_self,
    revoke_administrator,
    suspend_administrator,
)
from app.core.errors import ConflictError, NotFoundError
from app.domain.admin.entities import (
    AdminIdentity,
    AdminPrivilege,
    AdminRole,
    AdminStatus,
)
from app.domain.security.entities import SecurityEventType
from app.domain.shared import UserId, new_id, utcnow
from app.domain.users.entities import Email, User
from tests.unit.application.fakes import (
    FakeAdminPrivilegeRepository,
    FakeAdminRepository,
    FakeAdminRoleRepository,
    FakeUserRepository,
)
from tests.unit.application.security_fakes import FakeSecurityEventRepository

TOKEN_SECRET = "test-secret"


class Harness:
    """An administrator store with one active superadmin already in it."""

    def __init__(self) -> None:
        self.admins = FakeAdminRepository()
        self.roles = FakeAdminRoleRepository()
        self.privileges = FakeAdminPrivilegeRepository()
        self.users = FakeUserRepository()
        self.events = FakeSecurityEventRepository()
        self.actor_id = UserId(new_id())

    async def add_admin(
        self,
        *,
        roles: tuple[str, ...] = (),
        status: str = AdminStatus.ACTIVE,
        email: str = "admin@example.com",
    ) -> AdminIdentity:
        user = User(email=Email(email), display_name="Admin", id=UserId(new_id()))
        await self.users.add(user)
        admin = AdminIdentity(
            user_id=user.id,
            status=AdminStatus(status),
            mfa_enrolled_at=utcnow() if status != AdminStatus.INVITED else None,
        )
        await self.admins.add(admin)
        for name in roles:
            await self.roles.assign(admin.id, AdminRole(name), assigned_by=None)
        return admin

    async def context_for(self, admin: AdminIdentity) -> AdminContext:
        return await build_context(
            admin.user_id,
            admins=self.admins,
            roles=self.roles,
            privileges=self.privileges,
            mfa_satisfied=True,
        )

    async def superadmin(self) -> AdminContext:
        admin = await self.add_admin(
            roles=(AdminRole.SUPERADMIN,), email="super@example.com"
        )
        return await self.context_for(admin)


@pytest.fixture
def harness() -> Harness:
    return Harness()


async def _suspend(harness: Harness, actor: AdminContext, target: AdminIdentity):
    return await suspend_administrator(
        actor,
        target.id,
        admins=harness.admins,
        roles=harness.roles,
        privileges=harness.privileges,
        security_events=harness.events,
    )


class TestReadUseCases:
    async def test_listing_requires_the_read_privilege(self, harness: Harness) -> None:
        actor = await harness.context_for(await harness.add_admin())
        with pytest.raises(MissingPrivilege):
            await list_administrators(
                actor,
                admins=harness.admins,
                roles=harness.roles,
                privileges=harness.privileges,
                users=harness.users,
            )

    async def test_listing_summarizes_admins_without_secrets(self, harness: Harness) -> None:
        context = await harness.superadmin()
        await harness.add_admin(email="other@example.com")

        summaries = await list_administrators(
            context,
            admins=harness.admins,
            roles=harness.roles,
            privileges=harness.privileges,
            users=harness.users,
        )

        assert len(summaries) == 2
        assert {s.email for s in summaries} == {"super@example.com", "other@example.com"}

    async def test_getting_an_unknown_administrator_is_a_not_found(
        self, harness: Harness
    ) -> None:
        context = await harness.superadmin()
        with pytest.raises(NotFoundError):
            await get_administrator(
                context,
                new_id(),
                admins=harness.admins,
                roles=harness.roles,
                privileges=harness.privileges,
                users=harness.users,
            )

    async def test_roles_and_privileges_catalogues_are_listed(self, harness: Harness) -> None:
        context = await harness.superadmin()
        assert AdminRole.SUPPORT_ADMIN in await list_roles(context, roles=harness.roles)
        assert AdminPrivilege.USERS_READ in await list_privileges(
            context, privileges=harness.privileges
        )


class TestLifecycle:
    async def test_suspend_then_reactivate(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(email="target@example.com")

        suspended = await _suspend(harness, context, target)
        assert suspended.status == AdminStatus.SUSPENDED

        reactivated = await reactivate_administrator(
            context,
            target.id,
            admins=harness.admins,
            roles=harness.roles,
            privileges=harness.privileges,
            security_events=harness.events,
        )
        assert reactivated.status == AdminStatus.ACTIVE

    async def test_suspend_emits_an_audit_event(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(email="target@example.com")

        await _suspend(harness, context, target)

        events = [e for e in harness.events.events if e.event_type == SecurityEventType.ADMIN_SUSPENDED]
        assert len(events) == 1
        assert events[0].metadata["admin_id"] == str(target.id)

    async def test_a_suspended_admin_can_no_longer_act(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(
            roles=(AdminRole.SUPPORT_ADMIN,), email="target@example.com"
        )

        await _suspend(harness, context, target)

        # Authorization is resolved afresh on every request, so the suspended
        # administrator's next attempt fails at context construction.
        with pytest.raises(AdministratorMayNotAct):
            await harness.context_for(target)

    async def test_suspending_an_already_suspended_admin_conflicts(
        self, harness: Harness
    ) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(email="target@example.com")
        await _suspend(harness, context, target)

        with pytest.raises(ConflictError):
            await _suspend(harness, context, target)

    async def test_reactivating_an_active_admin_conflicts(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(email="target@example.com")
        with pytest.raises(ConflictError):
            await reactivate_administrator(
                context,
                target.id,
                admins=harness.admins,
                roles=harness.roles,
                privileges=harness.privileges,
                security_events=harness.events,
            )

    async def test_revoke_is_terminal_for_access(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(
            roles=(AdminRole.SUPPORT_ADMIN,), email="target@example.com"
        )

        revoked = await revoke_administrator(
            context,
            target.id,
            admins=harness.admins,
            roles=harness.roles,
            privileges=harness.privileges,
            security_events=harness.events,
        )

        assert revoked.status == AdminStatus.REVOKED
        with pytest.raises(ConflictError):
            await _suspend(harness, context, revoked)

    async def test_revoking_emits_an_audit_event(self, harness: Harness) -> None:
        context = await harness.superadmin()
        target = await harness.add_admin(email="target@example.com")
        await revoke_administrator(
            context,
            target.id,
            admins=harness.admins,
            roles=harness.roles,
            privileges=harness.privileges,
            security_events=harness.events,
        )
        assert any(
            e.event_type == SecurityEventType.ADMIN_REVOKED for e in harness.events.events
        )

    async def test_an_admin_without_the_manage_privilege_cannot_suspend(
        self, harness: Harness
    ) -> None:
        actor_admin = await harness.add_admin(
            roles=(AdminRole.SUPPORT_ADMIN,), email="actor@example.com"
        )
        actor = await harness.context_for(actor_admin)
        target = await harness.add_admin(email="target@example.com")

        with pytest.raises(MissingPrivilege):
            await _suspend(harness, actor, target)

    async def test_only_a_superadmin_may_manage_a_superadmin(self, harness: Harness) -> None:
        actor_admin = await harness.add_admin(
            roles=(AdminRole.OPERATIONS_ADMIN,), email="actor@example.com"
        )
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        superadmin = await harness.add_admin(
            roles=(AdminRole.SUPERADMIN,), email="super@example.com"
        )

        with pytest.raises(ConflictError):
            await _suspend(harness, actor, superadmin)

    async def test_an_administrator_cannot_change_its_own_lifecycle_state(
        self, harness: Harness
    ) -> None:
        context = await harness.superadmin()

        with pytest.raises(ConflictError):
            await require_not_self(context, context.admin.id)
