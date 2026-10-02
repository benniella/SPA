"""Effective privilege resolution and the administrative authorization boundary."""

from __future__ import annotations

import pytest

from app.application.admin_authz import (
    AdministratorMayNotAct,
    MfaNotSatisfied,
    MissingPrivilege,
    NotAnAdministrator,
    build_context,
    effective_privileges,
    role_privileges,
)
from app.domain.admin.catalogue import ROLE_PRIVILEGES
from app.domain.admin.entities import (
    AdminIdentity,
    AdminPrivilege,
    AdminRole,
    AdminStatus,
)
from app.domain.shared import UserId, new_id, utcnow
from tests.unit.application.fakes import (
    FakeAdminPrivilegeRepository,
    FakeAdminRepository,
    FakeAdminRoleRepository,
)


def _active_admin() -> AdminIdentity:
    return AdminIdentity(
        user_id=UserId(new_id()),
        status=AdminStatus(AdminStatus.ACTIVE),
        mfa_enrolled_at=utcnow(),
    )


class TestRolePrivileges:
    def test_a_role_grants_exactly_what_the_catalogue_says(self) -> None:
        for name, privileges in ROLE_PRIVILEGES.items():
            assert role_privileges(AdminRole(name)) == frozenset(privileges)

    def test_superadmin_grants_every_privilege(self) -> None:
        assert role_privileges(AdminRole(AdminRole.SUPERADMIN)) == frozenset(AdminPrivilege.ALLOWED)


class TestEffectivePrivileges:
    async def test_roles_are_unioned_with_direct_grants(self) -> None:
        admin = _active_admin()
        roles = FakeAdminRoleRepository()
        privileges = FakeAdminPrivilegeRepository()
        await roles.assign(admin.id, AdminRole(AdminRole.SUPPORT_ADMIN), assigned_by=None)
        await privileges.grant(
            admin.id, AdminPrivilege(AdminPrivilege.SECURITY_READ), granted_by=None
        )

        held = await effective_privileges(admin.id, roles=roles, privileges=privileges)

        assert AdminPrivilege.SUPPORT_MANAGE in held
        assert AdminPrivilege.SECURITY_READ in held
        assert AdminPrivilege.BILLING_MANAGE not in held

    async def test_removing_a_role_removes_its_privileges_immediately(self) -> None:
        admin = _active_admin()
        roles = FakeAdminRoleRepository()
        privileges = FakeAdminPrivilegeRepository()
        await roles.assign(admin.id, AdminRole(AdminRole.SECURITY_ADMIN), assigned_by=None)
        assert AdminPrivilege.SECURITY_MANAGE in await effective_privileges(
            admin.id, roles=roles, privileges=privileges
        )

        await roles.unassign(admin.id, AdminRole(AdminRole.SECURITY_ADMIN))

        assert AdminPrivilege.SECURITY_MANAGE not in await effective_privileges(
            admin.id, roles=roles, privileges=privileges
        )

    async def test_an_admin_with_no_roles_holds_nothing(self) -> None:
        held = await effective_privileges(
            new_id(), roles=FakeAdminRoleRepository(), privileges=FakeAdminPrivilegeRepository()
        )
        assert held == frozenset()


class TestBuildContext:
    async def _context(self, admin, *, mfa_satisfied=True, roles=None, privileges=None):
        admins = FakeAdminRepository()
        await admins.add(admin)
        return await build_context(
            admin.user_id,
            admins=admins,
            roles=roles or FakeAdminRoleRepository(),
            privileges=privileges or FakeAdminPrivilegeRepository(),
            mfa_satisfied=mfa_satisfied,
        )

    async def test_an_ordinary_user_is_refused(self) -> None:
        with pytest.raises(NotAnAdministrator):
            await build_context(
                UserId(new_id()),
                admins=FakeAdminRepository(),
                roles=FakeAdminRoleRepository(),
                privileges=FakeAdminPrivilegeRepository(),
                mfa_satisfied=True,
            )

    async def test_a_suspended_admin_is_refused(self) -> None:
        admin = AdminIdentity(
            user_id=UserId(new_id()),
            status=AdminStatus(AdminStatus.SUSPENDED),
            mfa_enrolled_at=utcnow(),
        )
        with pytest.raises(AdministratorMayNotAct):
            await self._context(admin)

    async def test_a_revoked_admin_is_refused(self) -> None:
        admin = AdminIdentity(
            user_id=UserId(new_id()),
            status=AdminStatus(AdminStatus.REVOKED),
            mfa_enrolled_at=utcnow(),
        )
        with pytest.raises(AdministratorMayNotAct):
            await self._context(admin)

    async def test_an_admin_without_mfa_enrolment_is_refused(self) -> None:
        admin = AdminIdentity(user_id=UserId(new_id()), status=AdminStatus(AdminStatus.ACTIVE))
        with pytest.raises(MfaNotSatisfied):
            await self._context(admin)

    async def test_a_session_without_mfa_is_refused(self) -> None:
        with pytest.raises(MfaNotSatisfied):
            await self._context(_active_admin(), mfa_satisfied=False)

    async def test_an_active_enrolled_admin_with_mfa_passes(self) -> None:
        roles = FakeAdminRoleRepository()
        admin = _active_admin()
        await roles.assign(admin.id, AdminRole(AdminRole.SUPPORT_ADMIN), assigned_by=None)

        context = await self._context(admin, roles=roles)

        assert not context.is_superadmin
        assert context.holds(AdminPrivilege.SUPPORT_MANAGE)

    async def test_superadmin_holds_every_privilege(self) -> None:
        roles = FakeAdminRoleRepository()
        admin = _active_admin()
        await roles.assign(admin.id, AdminRole(AdminRole.SUPERADMIN), assigned_by=None)

        context = await self._context(admin, roles=roles)

        assert context.is_superadmin
        for privilege in AdminPrivilege.ALLOWED:
            assert context.holds(privilege)

    async def test_require_raises_for_a_privilege_that_is_not_held(self) -> None:
        context = await self._context(_active_admin())
        with pytest.raises(MissingPrivilege):
            context.require(AdminPrivilege.BILLING_MANAGE)
