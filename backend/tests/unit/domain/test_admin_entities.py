"""Admin domain rules: status gating, invitation lifecycle, MFA challenges."""

from __future__ import annotations

from datetime import timedelta

from app.domain.admin.catalogue import ROLE_PRIVILEGES
from app.domain.admin.entities import (
    AdminIdentity,
    AdminInvitation,
    AdminMfaChallenge,
    AdminPrivilege,
    AdminRole,
    AdminStatus,
)
from app.domain.shared import UserId, new_id, utcnow


def _user_id() -> UserId:
    return UserId(new_id())


class TestAdminIdentity:
    def test_an_active_enrolled_admin_with_satisfied_mfa_can_act(self) -> None:
        admin = AdminIdentity(
            user_id=_user_id(), status=AdminStatus(AdminStatus.ACTIVE), mfa_enrolled_at=utcnow()
        )
        assert admin.can_act(mfa_satisfied=True)

    def test_no_mfa_enrolment_blocks_access(self) -> None:
        admin = AdminIdentity(user_id=_user_id(), status=AdminStatus(AdminStatus.ACTIVE))
        assert not admin.can_act(mfa_satisfied=True)

    def test_unsatisfied_mfa_blocks_access(self) -> None:
        admin = AdminIdentity(
            user_id=_user_id(), status=AdminStatus(AdminStatus.ACTIVE), mfa_enrolled_at=utcnow()
        )
        assert not admin.can_act(mfa_satisfied=False)

    def test_suspended_and_revoked_block_access(self) -> None:
        for status in (AdminStatus.SUSPENDED, AdminStatus.REVOKED, AdminStatus.INVITED):
            admin = AdminIdentity(
                user_id=_user_id(),
                status=AdminStatus(status),
                mfa_enrolled_at=utcnow(),
            )
            assert not admin.can_act(mfa_satisfied=True)


class TestAdminInvitation:
    def test_a_fresh_invitation_is_usable(self) -> None:
        invitation = AdminInvitation(
            email="someone@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=_user_id(),
        )
        assert invitation.is_usable()

    def test_accepting_makes_it_unusable(self) -> None:
        invitation = AdminInvitation(
            email="someone@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=None,
        )
        invitation.accept()
        assert not invitation.is_usable()
        invitation.revoke()
        assert invitation.is_revoked

    def test_revoking_twice_keeps_the_first_timestamp(self) -> None:
        invitation = AdminInvitation(
            email="someone@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="hash",
            expires_at=utcnow() + timedelta(days=7),
            invited_by=None,
        )
        invitation.revoke()
        first = invitation.revoked_at
        invitation.revoke()
        assert invitation.revoked_at == first

    def test_an_expired_invitation_is_not_usable(self) -> None:
        invitation = AdminInvitation(
            email="someone@example.com",
            role=AdminRole(AdminRole.SUPPORT_ADMIN),
            token_hash="hash",
            expires_at=utcnow() - timedelta(seconds=1),
            invited_by=None,
        )
        assert not invitation.is_usable()


class TestAdminMfaChallenge:
    def test_attempt_exhaustion(self) -> None:
        challenge = AdminMfaChallenge(
            admin_id=new_id(),
            session_id=new_id(),
            expires_at=utcnow() + timedelta(minutes=5),
            max_attempts=2,
        )
        challenge.register_attempt()
        assert not challenge.attempts_exhausted
        challenge.register_attempt()
        assert challenge.attempts_exhausted

    def test_satisfaction_is_final_and_expiry_binds_it(self) -> None:
        challenge = AdminMfaChallenge(
            admin_id=new_id(),
            session_id=new_id(),
            expires_at=utcnow() - timedelta(seconds=1),
        )
        assert challenge.is_expired()
        challenge.satisfy()
        assert challenge.is_satisfied


class TestCatalogue:
    def test_every_role_privilege_is_a_known_privilege(self) -> None:
        for role, privileges in ROLE_PRIVILEGES.items():
            assert AdminRole(role) == role
            for privilege in privileges:
                assert AdminPrivilege(privilege) == privilege

    def test_superadmin_holds_every_privilege(self) -> None:
        assert set(ROLE_PRIVILEGES[AdminRole.SUPERADMIN]) == set(AdminPrivilege.ALLOWED)
