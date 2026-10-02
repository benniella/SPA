"""Platform-administration persistence against a real database.

The catalogue tables are seeded by the migration, and this suite truncates every
table first, so each test seeds the catalogue rows it needs from the domain
catalogue. That keeps the assertions about behaviour rather than about whatever
rows happened to survive.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
import sqlalchemy as sa

from app.domain.admin.catalogue import PRIVILEGE_DESCRIPTIONS, ROLE_PRIVILEGES
from app.domain.admin.entities import (
    AdminIdentity,
    AdminInvitation,
    AdminPrivilege,
    AdminRole,
    AdminStatus,
)
from app.domain.shared import UserId, utcnow
from app.infrastructure.database.engine import session_scope
from app.infrastructure.database.unit_of_work import SqlAlchemyUnitOfWork

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("clean_database")]


@pytest.fixture
async def session_factory():
    from app.core.config import get_settings
    from app.infrastructure.database.engine import get_session_factory

    return get_session_factory(get_settings())


@pytest.fixture
def uow_factory(session_factory):
    return lambda: SqlAlchemyUnitOfWork(session_factory)


async def _seed_catalogue(session_factory) -> None:
    from app.domain.admin.catalogue import ROLE_DESCRIPTIONS

    async with session_scope(session_factory) as session:
        privilege_ids: dict[str, uuid.UUID] = {}
        for name in PRIVILEGE_DESCRIPTIONS:
            privilege_id = uuid.uuid4()
            privilege_ids[name] = privilege_id
            await session.execute(
                sa.text(
                    "INSERT INTO admin_privileges (id, name, description) "
                    "VALUES (:id, :name, :description)"
                ),
                {"id": privilege_id, "name": name, "description": name},
            )
        for role_name in ROLE_DESCRIPTIONS:
            role_id = uuid.uuid4()
            await session.execute(
                sa.text(
                    "INSERT INTO admin_roles (id, name, description) "
                    "VALUES (:id, :name, :description)"
                ),
                {"id": role_id, "name": role_name, "description": role_name},
            )
            for privilege_name in ROLE_PRIVILEGES[role_name]:
                await session.execute(
                    sa.text(
                        "INSERT INTO admin_role_privileges (id, role_id, privilege_id) "
                        "VALUES (:id, :role_id, :privilege_id)"
                    ),
                    {
                        "id": uuid.uuid4(),
                        "role_id": role_id,
                        "privilege_id": privilege_ids[privilege_name],
                    },
                )
        await session.commit()


async def _make_user(session_factory) -> UserId:
    from app.infrastructure.database.models import UserModel

    user_id = uuid.uuid4()
    async with session_scope(session_factory) as session:
        session.add(
            UserModel(
                id=user_id,
                email=f"{user_id}@example.com",
                display_name="Admin Candidate",
                is_active=True,
            )
        )
        await session.commit()
    return UserId(user_id)


@pytest.fixture
async def seeded(session_factory):
    await _seed_catalogue(session_factory)
    return session_factory


class TestAdminIdentityPersistence:
    async def test_round_trip(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(
            user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE), mfa_enrolled_at=utcnow()
        )
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.commit()

        async with uow_factory() as uow:
            loaded = await uow.admins.get_by_user(user_id)
        assert loaded is not None
        assert loaded.id == admin.id
        assert loaded.status == AdminStatus.ACTIVE
        assert loaded.is_mfa_enrolled

    async def test_status_transition_persists_and_blocks_access(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(
            user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE), mfa_enrolled_at=utcnow()
        )
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.commit()

        suspended = AdminIdentity(
            user_id=admin.user_id,
            status=AdminStatus(AdminStatus.SUSPENDED),
            id=admin.id,
            mfa_enrolled_at=admin.mfa_enrolled_at,
        )
        async with uow_factory() as uow:
            await uow.admins.update(suspended)
            await uow.commit()

        async with uow_factory() as uow:
            loaded = await uow.admins.get(admin.id)
        assert loaded is not None
        assert loaded.status == AdminStatus.SUSPENDED
        assert not loaded.can_act(mfa_satisfied=True)

    async def test_a_user_cannot_hold_two_admin_records(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        first = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(first)
            await uow.commit()

        second = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.INVITED))
        with pytest.raises(sa.exc.IntegrityError):
            async with uow_factory() as uow:
                await uow.admins.add(second)
                await uow.commit()


class TestRolesAndPrivileges:
    async def test_assigning_a_role_confers_its_privileges(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.admin_roles.assign(
                admin.id, AdminRole(AdminRole.SECURITY_ADMIN), assigned_by=None
            )
            await uow.commit()

        async with uow_factory() as uow:
            roles = await uow.admin_roles.roles_for_admin(admin.id)
            privileges = set(await uow.admin_privileges.privileges_for_admin(admin.id))

        assert [str(role) for role in roles] == [AdminRole.SECURITY_ADMIN]
        assert AdminPrivilege(AdminPrivilege.SECURITY_MANAGE) in privileges
        assert AdminPrivilege(AdminPrivilege.USERS_SUSPEND) in privileges
        assert AdminPrivilege(AdminPrivilege.BILLING_MANAGE) not in privileges

    async def test_removing_a_role_removes_its_privileges_immediately(
        self, seeded, uow_factory
    ) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.admin_roles.assign(
                admin.id, AdminRole(AdminRole.SUPPORT_ADMIN), assigned_by=None
            )
            await uow.commit()

        async with uow_factory() as uow:
            await uow.admin_roles.unassign(admin.id, AdminRole(AdminRole.SUPPORT_ADMIN))
            await uow.commit()

        async with uow_factory() as uow:
            roles = await uow.admin_roles.roles_for_admin(admin.id)
            privileges = await uow.admin_privileges.privileges_for_admin(admin.id)
        assert roles == []
        assert privileges == []

    async def test_a_direct_grant_adds_to_role_privileges(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.admin_roles.assign(
                admin.id, AdminRole(AdminRole.FINANCE_ADMIN), assigned_by=None
            )
            await uow.admin_privileges.grant(
                admin.id, AdminPrivilege(AdminPrivilege.SECURITY_READ), granted_by=None
            )
            await uow.commit()

        async with uow_factory() as uow:
            privileges = set(await uow.admin_privileges.privileges_for_admin(admin.id))
        assert AdminPrivilege(AdminPrivilege.BILLING_MANAGE) in privileges
        assert AdminPrivilege(AdminPrivilege.SECURITY_READ) in privileges

        async with uow_factory() as uow:
            await uow.admin_privileges.revoke(
                admin.id, AdminPrivilege(AdminPrivilege.SECURITY_READ)
            )
            await uow.commit()

        async with uow_factory() as uow:
            privileges = set(await uow.admin_privileges.privileges_for_admin(admin.id))
        assert AdminPrivilege(AdminPrivilege.SECURITY_READ) not in privileges
        assert AdminPrivilege(AdminPrivilege.BILLING_MANAGE) in privileges

    async def test_a_role_not_in_the_catalogue_is_refused(self, seeded, uow_factory) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.commit()

        # Seeding removes the catalogue rows, so the name resolves to nothing and
        # assigning it must fail rather than silently write a dangling grant.
        async with session_scope(seeded) as session:
            await session.execute(sa.text("DELETE FROM admin_roles"))
            await session.commit()

        with pytest.raises(LookupError):
            async with uow_factory() as uow:
                await uow.admin_roles.assign(
                    admin.id, AdminRole(AdminRole.SUPERADMIN), assigned_by=None
                )
                await uow.commit()


class TestInvitations:
    async def _role_id(self, session_factory, name: str) -> uuid.UUID:
        async with session_scope(session_factory) as session:
            return await session.scalar(
                sa.text("SELECT id FROM admin_roles WHERE name = :name"), {"name": name}
            )

    async def test_round_trip_carries_the_role(self, seeded, uow_factory) -> None:
        role_id = await self._role_id(seeded, AdminRole.SUPPORT_ADMIN)
        invitation = AdminInvitation(
            email="candidate@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="token-hash-1",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=await _make_user(seeded),
        )
        async with uow_factory() as uow:
            await uow.admin_invitations.add(invitation, role_id=role_id)
            await uow.commit()

        async with uow_factory() as uow:
            found = await uow.admin_invitations.get_by_token_hash("token-hash-1")
        assert found is not None
        loaded, loaded_role_id = found
        assert loaded.email == "candidate@example.com"
        assert loaded.role == AdminRole.SUPPORT_ADMIN
        assert loaded_role_id == role_id

    async def test_token_hash_is_unique(self, seeded, uow_factory) -> None:
        role_id = await self._role_id(seeded, AdminRole.SUPPORT_ADMIN)
        inviter = await _make_user(seeded)
        first = AdminInvitation(
            email="one@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="shared-hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=inviter,
        )
        second = AdminInvitation(
            email="two@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="shared-hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=inviter,
        )
        async with uow_factory() as uow:
            await uow.admin_invitations.add(first, role_id=role_id)
            await uow.commit()
        with pytest.raises(sa.exc.IntegrityError):
            async with uow_factory() as uow:
                await uow.admin_invitations.add(second, role_id=role_id)
                await uow.commit()

    async def test_accepting_revokes_nothing_but_marks_it_accepted(
        self, seeded, uow_factory
    ) -> None:
        role_id = await self._role_id(seeded, AdminRole.SUPPORT_ADMIN)
        invitation = AdminInvitation(
            email="candidate@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="accept-hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=None,
        )
        async with uow_factory() as uow:
            await uow.admin_invitations.add(invitation, role_id=role_id)
            await uow.commit()

        invitation.accept()
        async with uow_factory() as uow:
            await uow.admin_invitations.update(invitation)
            await uow.commit()

        async with uow_factory() as uow:
            found = await uow.admin_invitations.get(invitation.id)
        assert found is not None
        assert found[0].is_accepted
        assert not found[0].is_usable()

    async def test_invalidating_an_address_revokes_only_outstanding_offers(
        self, seeded, uow_factory
    ) -> None:
        role_id = await self._role_id(seeded, AdminRole.SUPPORT_ADMIN)
        inviter = await _make_user(seeded)
        outstanding = AdminInvitation(
            email="person@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="outstanding",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=inviter,
        )
        accepted = AdminInvitation(
            email="person@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="accepted",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=inviter,
        )
        accepted.accept()
        async with uow_factory() as uow:
            await uow.admin_invitations.add(outstanding, role_id=role_id)
            await uow.admin_invitations.add(accepted, role_id=role_id)
            await uow.commit()

        async with uow_factory() as uow:
            revoked = await uow.admin_invitations.invalidate_for_email("person@example.com")
            await uow.commit()
        assert revoked == 1

        async with uow_factory() as uow:
            still_outstanding = await uow.admin_invitations.get_by_token_hash("outstanding")
            already_accepted = await uow.admin_invitations.get_by_token_hash("accepted")
        assert still_outstanding is not None and still_outstanding[0].is_revoked
        assert already_accepted is not None and not already_accepted[0].is_revoked

    async def test_latest_for_email_returns_the_newest(self, seeded, uow_factory) -> None:
        role_id = await self._role_id(seeded, AdminRole.SUPPORT_ADMIN)
        inviter = await _make_user(seeded)
        for token_hash in ("oldest", "newer", "newest"):
            async with uow_factory() as uow:
                await uow.admin_invitations.add(
                    AdminInvitation(
                        email="person@example.com",
                        role=AdminRole(AdminRole.SUPPORT_ADMIN),
                        token_hash=token_hash,
                        expires_at=utcnow() + timedelta(days=7),
                        invited_by=inviter,
                    ),
                    role_id=role_id,
                )
                await uow.commit()

        async with uow_factory() as uow:
            latest = await uow.admin_invitations.latest_for_email("person@example.com")
        assert latest is not None
        assert latest.token_hash == "newest"


class TestMfaPersistence:
    async def _admin(self, seeded, uow_factory) -> AdminIdentity:
        admin = AdminIdentity(
            user_id=await _make_user(seeded), status=AdminStatus(AdminStatus.ACTIVE)
        )
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.commit()
        return admin

    async def test_enrolment_round_trip(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_secret(admin.id) is None
            assert not await uow.admin_mfa.is_confirmed(admin.id)
            await uow.admin_mfa.set_secret(admin.id, secret_encrypted="enc:abc")
            await uow.admin_mfa.confirm(admin.id)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_secret(admin.id) == "enc:abc"
            assert await uow.admin_mfa.is_confirmed(admin.id)

    async def test_setting_a_secret_twice_updates_rather_than_duplicates(
        self, seeded, uow_factory
    ) -> None:
        admin = await self._admin(seeded, uow_factory)
        async with uow_factory() as uow:
            await uow.admin_mfa.set_secret(admin.id, secret_encrypted="enc:first")
            await uow.admin_mfa.set_secret(admin.id, secret_encrypted="enc:second")
            await uow.commit()
        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_secret(admin.id) == "enc:second"

    async def test_a_recovery_code_is_single_use(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        async with uow_factory() as uow:
            await uow.admin_mfa.replace_recovery_codes(admin.id, code_hashes=["hash-a", "hash-b"])
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="hash-a")
            await uow.commit()
        async with uow_factory() as uow:
            assert not await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="hash-a")
            assert await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="hash-b")
            await uow.commit()

    async def test_regenerating_invalidates_previous_codes(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        async with uow_factory() as uow:
            await uow.admin_mfa.replace_recovery_codes(admin.id, code_hashes=["old-code"])
            await uow.commit()
        async with uow_factory() as uow:
            await uow.admin_mfa.replace_recovery_codes(admin.id, code_hashes=["new-code"])
            await uow.commit()

        async with uow_factory() as uow:
            assert not await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="old-code")
            assert await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="new-code")
            await uow.commit()

    async def test_clearing_removes_the_credential_and_every_code(
        self, seeded, uow_factory
    ) -> None:
        admin = await self._admin(seeded, uow_factory)
        async with uow_factory() as uow:
            await uow.admin_mfa.set_secret(admin.id, secret_encrypted="enc:abc")
            await uow.admin_mfa.confirm(admin.id)
            await uow.admin_mfa.replace_recovery_codes(admin.id, code_hashes=["code"])
            await uow.admin_mfa.clear(admin.id)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_secret(admin.id) is None
            assert not await uow.admin_mfa.is_confirmed(admin.id)
            assert not await uow.admin_mfa.consume_recovery_code(admin.id, code_hash="code")


class TestMfaChallenges:
    async def _admin(self, seeded, uow_factory) -> AdminIdentity:
        admin = AdminIdentity(
            user_id=await _make_user(seeded), status=AdminStatus(AdminStatus.ACTIVE)
        )
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.commit()
        return admin

    async def _session(self, session_factory, user_id) -> uuid.UUID:
        from app.infrastructure.database.models import SessionModel

        session_id = uuid.uuid4()
        async with session_scope(session_factory) as session:
            session.add(
                SessionModel(
                    id=session_id,
                    user_id=user_id,
                    token_hash=f"token-{session_id}",
                    expires_at=utcnow() + timedelta(hours=1),
                    last_used_at=utcnow(),
                )
            )
            await session.commit()
        return session_id

    async def test_a_challenge_is_bound_to_its_session(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        session_id = await self._session(seeded, admin.user_id)
        other_session = await self._session(seeded, admin.user_id)

        async with uow_factory() as uow:
            await uow.admin_mfa.start_challenge(
                admin.id,
                session_id=session_id,
                expires_at=utcnow() + timedelta(minutes=5),
                max_attempts=5,
            )
            await uow.commit()

        async with uow_factory() as uow:
            found = await uow.admin_mfa.get_challenge(admin.id, session_id)
            elsewhere = await uow.admin_mfa.get_challenge(admin.id, other_session)
        assert found is not None
        assert elsewhere is None

    async def test_attempts_are_recorded_and_exhaustion_hides_the_challenge(
        self, seeded, uow_factory
    ) -> None:
        admin = await self._admin(seeded, uow_factory)
        session_id = await self._session(seeded, admin.user_id)
        async with uow_factory() as uow:
            await uow.admin_mfa.start_challenge(
                admin.id,
                session_id=session_id,
                expires_at=utcnow() + timedelta(minutes=5),
                max_attempts=2,
            )
            await uow.commit()

        async with uow_factory() as uow:
            challenge = await uow.admin_mfa.get_challenge(admin.id, session_id)
            assert challenge is not None
            await uow.admin_mfa.record_challenge_attempt(challenge.id, attempts=2)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_challenge(admin.id, session_id) is None

    async def test_an_expired_challenge_is_not_returned(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        session_id = await self._session(seeded, admin.user_id)
        async with uow_factory() as uow:
            await uow.admin_mfa.start_challenge(
                admin.id,
                session_id=session_id,
                expires_at=utcnow() - timedelta(seconds=1),
                max_attempts=5,
            )
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_challenge(admin.id, session_id) is None

    async def test_satisfying_a_challenge_makes_it_unusable(self, seeded, uow_factory) -> None:
        admin = await self._admin(seeded, uow_factory)
        session_id = await self._session(seeded, admin.user_id)
        async with uow_factory() as uow:
            await uow.admin_mfa.start_challenge(
                admin.id,
                session_id=session_id,
                expires_at=utcnow() + timedelta(minutes=5),
                max_attempts=5,
            )
            await uow.commit()

        async with uow_factory() as uow:
            challenge = await uow.admin_mfa.get_challenge(admin.id, session_id)
            assert challenge is not None
            await uow.admin_mfa.satisfy_challenge(challenge.id)
            await uow.commit()

        async with uow_factory() as uow:
            assert await uow.admin_mfa.get_challenge(admin.id, session_id) is None


class TestCascade:
    async def test_removing_the_admin_removes_its_grants_and_challenges(
        self, seeded, uow_factory
    ) -> None:
        user_id = await _make_user(seeded)
        admin = AdminIdentity(user_id=user_id, status=AdminStatus(AdminStatus.ACTIVE))
        async with uow_factory() as uow:
            await uow.admins.add(admin)
            await uow.admin_roles.assign(
                admin.id, AdminRole(AdminRole.SUPPORT_ADMIN), assigned_by=None
            )
            await uow.admin_mfa.set_secret(admin.id, secret_encrypted="enc:abc")
            await uow.admin_mfa.replace_recovery_codes(admin.id, code_hashes=["code"])
            await uow.commit()

        async with session_scope(seeded) as session:
            await session.execute(
                sa.text("DELETE FROM platform_admins WHERE id = :id"), {"id": admin.id}
            )
            await session.commit()

        async with session_scope(seeded) as session:
            for table in (
                "admin_role_assignments",
                "admin_mfa_credentials",
                "admin_recovery_codes",
            ):
                remaining = await session.scalar(
                    sa.text(f"SELECT count(*) FROM {table} WHERE admin_id = :id"),
                    {"id": admin.id},
                )
                assert remaining == 0, table
