"""Production identity and account security.

Adds the credential, session, challenge, OTP and security-event tables, plus the
account-lifecycle columns on 'users'.

'users.account_status' carries a server default so the migration succeeds on a
database that already holds rows: the existing development users become 'active'
rather than being dropped or left unusable. The check constraint then guarantees
an out-of-band insert cannot create an account in an unknown state.

Revision ID: e639aa23a560
Revises: 20260930_0005
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e639aa23a560"
down_revision: str | None = "20260930_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "otp_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=64), nullable=False),
        sa.Column("destination", sa.String(length=320), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "purpose IN ('phone_verification', 'phone_removal', 'email_verification', 'account_recovery', 'sensitive_action')",
            name=op.f("ck_otp_challenges_otp_purpose_known"),
        ),
        sa.CheckConstraint(
            "attempts >= 0", name=op.f("ck_otp_challenges_otp_attempts_non_negative")
        ),
        sa.CheckConstraint(
            "max_attempts >= 1", name=op.f("ck_otp_challenges_otp_max_attempts_positive")
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_otp_challenges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_otp_challenges")),
    )
    op.create_index(
        op.f("ix_otp_challenges_code_hash"), "otp_challenges", ["code_hash"], unique=False
    )
    op.create_index(op.f("ix_otp_challenges_user_id"), "otp_challenges", ["user_id"], unique=False)
    op.create_index(
        "ix_otp_challenges_user_purpose", "otp_challenges", ["user_id", "purpose"], unique=False
    )
    op.create_table(
        "security_challenges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("destination", sa.String(length=320), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind IN ('email_verification', 'email_change', 'password_reset', 'recovery')",
            name=op.f("ck_security_challenges_security_challenge_kind_known"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_security_challenges_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_challenges")),
    )
    op.create_index(
        op.f("ix_security_challenges_token_hash"),
        "security_challenges",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_security_challenges_user_id"), "security_challenges", ["user_id"], unique=False
    )
    op.create_index(
        "ix_security_challenges_user_kind", "security_challenges", ["user_id", "kind"], unique=False
    )
    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("ip_prefix", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_security_events_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_security_events")),
    )
    op.create_index(
        "ix_security_events_type_created",
        "security_events",
        ["event_type", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_security_events_user_created",
        "security_events",
        ["user_id", "created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_security_events_user_id"), "security_events", ["user_id"], unique=False
    )
    op.create_table(
        "sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("ip_prefix", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= created_at",
            name=op.f("ck_sessions_session_revoked_after_creation"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_sessions_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sessions")),
    )
    op.create_index(op.f("ix_sessions_token_hash"), "sessions", ["token_hash"], unique=True)
    op.create_index("ix_sessions_user_expires", "sessions", ["user_id", "expires_at"], unique=False)
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.add_column(
        "users",
        sa.Column(
            "account_status",
            sa.String(length=32),
            server_default="active",
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "user_account_status_known",
        "users",
        "account_status IN ('pending_verification', 'active', 'suspended', 'deactivated')",
    )
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))
    op.add_column(
        "users", sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("phone_number", sa.String(length=32), nullable=True))
    op.add_column(
        "users", sa.Column("phone_verified_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "users", sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "last_login_at")
    op.drop_column("users", "phone_verified_at")
    op.drop_column("users", "phone_number")
    op.drop_column("users", "email_verified_at")
    op.drop_column("users", "password_hash")
    op.drop_constraint("ck_users_user_account_status_known", "users", type_="check")
    op.drop_column("users", "account_status")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_index("ix_sessions_user_expires", table_name="sessions")
    op.drop_index(op.f("ix_sessions_token_hash"), table_name="sessions")
    op.drop_table("sessions")
    op.drop_index(op.f("ix_security_events_user_id"), table_name="security_events")
    op.drop_index("ix_security_events_user_created", table_name="security_events")
    op.drop_index("ix_security_events_type_created", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_security_challenges_user_kind", table_name="security_challenges")
    op.drop_index(op.f("ix_security_challenges_user_id"), table_name="security_challenges")
    op.drop_index(op.f("ix_security_challenges_token_hash"), table_name="security_challenges")
    op.drop_table("security_challenges")
    op.drop_index("ix_otp_challenges_user_purpose", table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_user_id"), table_name="otp_challenges")
    op.drop_index(op.f("ix_otp_challenges_code_hash"), table_name="otp_challenges")
    op.drop_table("otp_challenges")
