"""Administrator invitation lifecycle and security."""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.application.admin_authz import MissingPrivilege, build_context
from app.application.use_cases.admin_invitations import (
    accept_invitation,
    create_invitation,
    resend_invitation,
    revoke_invitation,
)
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.domain.admin.entities import AdminIdentity, AdminRole, AdminStatus
from app.domain.security.entities import SecurityEventType
from app.domain.security.tokens import generate_token, hash_token
from app.domain.shared import UserId, new_id, utcnow
from app.domain.users.entities import Email, User
from tests.unit.application.fakes import (
    FakeAdminInvitationRepository,
    FakeAdminPrivilegeRepository,
    FakeAdminRepository,
    FakeAdminRoleRepository,
    FakeUserRepository,
)
from tests.unit.application.security_fakes import (
    FakeSecurityEventRepository,
    RecordingEmailSender,
)

TOKEN_SECRET = "test-secret"
BASE_URL = "https://app.example.com"


class Harness:
    def __init__(self) -> None:
        self.admins = FakeAdminRepository()
        self.roles = FakeAdminRoleRepository()
        self.privileges = FakeAdminPrivilegeRepository()
        self.invitations = FakeAdminInvitationRepository()
        self.users = FakeUserRepository()
        self.events = FakeSecurityEventRepository()
        self.email = RecordingEmailSender()

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


async def _create(harness: Harness, actor, *, email="new@example.com", role=AdminRole.SUPPORT_ADMIN):
    return await create_invitation(
        actor,
        email=email,
        role_name=role,
        roles=harness.roles,
        invitations=harness.invitations,
        security_events=harness.events,
        email_sender=harness.email,
        token_secret=TOKEN_SECRET,
        app_base_url=BASE_URL,
    )


class TestCreation:
    async def test_creation_persists_hashed_and_emails_the_token(
        self, harness: Harness
    ) -> None:
        actor = await harness.superadmin_context()

        issued = await _create(harness, actor)

        stored = await harness.invitations.get_by_token_hash(
            hash_token(issued.token, secret=TOKEN_SECRET)
        )
        assert stored is not None
        assert stored[0].email == "new@example.com"
        assert issued.token not in str(stored[0].token_hash)
        assert len(harness.email.messages) == 1
        assert issued.token in harness.email.messages[0].text

    async def test_creation_emits_an_audit_event(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        await _create(harness, actor)
        assert any(
            e.event_type == SecurityEventType.ADMIN_INVITATION_CREATED
            for e in harness.events.events
        )

    async def test_the_email_is_normalized(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor, email="  New@Example.COM ")
        assert issued.invitation.email == "new@example.com"

    async def test_a_second_active_invitation_for_the_same_address_conflicts(
        self, harness: Harness
    ) -> None:
        actor = await harness.superadmin_context()
        await _create(harness, actor)
        with pytest.raises(ConflictError):
            await _create(harness, actor)

    async def test_an_unknown_role_is_rejected(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        with pytest.raises(ValidationError):
            await _create(harness, actor, role="nope")

    async def test_an_invalid_email_is_rejected(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        with pytest.raises(ValidationError):
            await _create(harness, actor, email="not-an-address")

    async def test_a_support_admin_cannot_invite_a_finance_admin(self, harness: Harness) -> None:
        from app.domain.admin.entities import AdminPrivilege

        actor_admin = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        with pytest.raises(ConflictError):
            await _create(harness, actor, role=AdminRole.FINANCE_ADMIN)

    async def test_a_support_admin_cannot_invite_a_superadmin(self, harness: Harness) -> None:
        from app.domain.admin.entities import AdminPrivilege

        actor_admin = await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        await harness.privileges.grant(
            actor_admin.id, AdminPrivilege(AdminPrivilege.ADMINS_MANAGE), granted_by=None
        )
        actor = await harness.context_for(actor_admin)
        with pytest.raises(ConflictError):
            await _create(harness, actor, role=AdminRole.SUPERADMIN)

    async def test_an_admin_without_the_privilege_cannot_invite(self, harness: Harness) -> None:
        actor = await harness.context_for(
            await harness.add_admin(roles=(AdminRole.SUPPORT_ADMIN,))
        )
        with pytest.raises(MissingPrivilege):
            await _create(harness, actor)


class TestResendAndRevoke:
    async def test_resend_rotates_the_token(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)

        resent = await resend_invitation(
            actor,
            issued.invitation.id,
            invitations=harness.invitations,
            security_events=harness.events,
            email_sender=harness.email,
            token_secret=TOKEN_SECRET,
            app_base_url=BASE_URL,
        )

        assert resent.token != issued.token
        old = await harness.invitations.get_by_token_hash(
            hash_token(issued.token, secret=TOKEN_SECRET)
        )
        new = await harness.invitations.get_by_token_hash(
            hash_token(resent.token, secret=TOKEN_SECRET)
        )
        assert old is None
        assert new is not None

    async def test_resend_emits_an_audit_event(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        await resend_invitation(
            actor,
            issued.invitation.id,
            invitations=harness.invitations,
            security_events=harness.events,
            email_sender=harness.email,
            token_secret=TOKEN_SECRET,
            app_base_url=BASE_URL,
        )
        assert any(
            e.event_type == SecurityEventType.ADMIN_INVITATION_RESENT
            for e in harness.events.events
        )

    async def test_a_revoked_invitation_cannot_be_resent(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        await revoke_invitation(
            actor,
            issued.invitation.id,
            invitations=harness.invitations,
            security_events=harness.events,
        )
        with pytest.raises(ConflictError):
            await resend_invitation(
                actor,
                issued.invitation.id,
                invitations=harness.invitations,
                security_events=harness.events,
                email_sender=harness.email,
                token_secret=TOKEN_SECRET,
                app_base_url=BASE_URL,
            )

    async def test_revocation_makes_the_token_unusable(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)

        await revoke_invitation(
            actor,
            issued.invitation.id,
            invitations=harness.invitations,
            security_events=harness.events,
        )

        assert any(
            e.event_type == SecurityEventType.ADMIN_INVITATION_REVOKED
            for e in harness.events.events
        )
        user = await _make_user(harness, "new@example.com")
        with pytest.raises(ConflictError):
            await _accept(harness, issued.token, user)

    async def test_revoking_twice_conflicts(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        await revoke_invitation(
            actor,
            issued.invitation.id,
            invitations=harness.invitations,
            security_events=harness.events,
        )
        with pytest.raises(ConflictError):
            await revoke_invitation(
                actor,
                issued.invitation.id,
                invitations=harness.invitations,
                security_events=harness.events,
            )


async def _make_user(harness: Harness, email: str) -> User:
    user = User(email=Email(email), display_name="Invitee", id=UserId(new_id()))
    await harness.users.add(user)
    return user


async def _accept(harness: Harness, token: str, user: User):
    return await accept_invitation(
        token=token,
        user_id=user.id,
        invitations=harness.invitations,
        admins=harness.admins,
        roles=harness.roles,
        users=harness.users,
        security_events=harness.events,
        token_secret=TOKEN_SECRET,
    )


class TestAcceptance:
    async def test_acceptance_creates_an_invited_not_active_admin(
        self, harness: Harness
    ) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        user = await _make_user(harness, "new@example.com")

        accepted = await _accept(harness, issued.token, user)

        assert accepted.admin.status == AdminStatus.INVITED
        assert not accepted.admin.is_mfa_enrolled
        stored = await harness.admins.get(accepted.admin.id)
        assert stored is not None and stored.status == AdminStatus.INVITED

    async def test_acceptance_applies_the_invited_role(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor, role=AdminRole.SECURITY_ADMIN)
        user = await _make_user(harness, "new@example.com")

        accepted = await _accept(harness, issued.token, user)

        held = [str(role) for role in await harness.roles.roles_for_admin(accepted.admin.id)]
        assert held == [AdminRole.SECURITY_ADMIN]

    async def test_an_invitation_is_single_use(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        user = await _make_user(harness, "new@example.com")

        await _accept(harness, issued.token, user)

        with pytest.raises(ConflictError):
            await _accept(harness, issued.token, user)

    async def test_an_expired_invitation_is_rejected(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        issued.invitation.expires_at = utcnow() - timedelta(seconds=1)
        await harness.invitations.update(issued.invitation)
        user = await _make_user(harness, "new@example.com")

        with pytest.raises(ConflictError):
            await _accept(harness, issued.token, user)

    async def test_a_malformed_token_is_not_found(self, harness: Harness) -> None:
        user = await _make_user(harness, "new@example.com")
        with pytest.raises(NotFoundError):
            await _accept(harness, generate_token(), user)

    async def test_the_wrong_recipient_is_rejected(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        intruder = await _make_user(harness, "someone.else@example.com")

        with pytest.raises(ConflictError):
            await _accept(harness, issued.token, intruder)

    async def test_acceptance_emits_an_audit_event(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        user = await _make_user(harness, "new@example.com")
        await _accept(harness, issued.token, user)
        assert any(
            e.event_type == SecurityEventType.ADMIN_INVITATION_ACCEPTED
            for e in harness.events.events
        )

    async def test_an_existing_administrator_cannot_accept(self, harness: Harness) -> None:
        actor = await harness.superadmin_context()
        issued = await _create(harness, actor)
        user = await _make_user(harness, "new@example.com")
        existing = AdminIdentity(user_id=user.id, status=AdminStatus(AdminStatus.ACTIVE))
        await harness.admins.add(existing)

        with pytest.raises(ConflictError):
            await _accept(harness, issued.token, user)
