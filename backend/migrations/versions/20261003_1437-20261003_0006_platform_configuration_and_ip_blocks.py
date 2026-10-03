"""Platform runtime configuration and auditable IP blocks.

Two additive tables: 'platform_settings' stores values for the declared setting
registry, and 'ip_blocks' stores network denials. Neither carries a secret.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "20261003_0006"
down_revision: str | None = "a1db7fc570c3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ip_blocks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("network", sa.String(length=64), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=300), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True),
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
            "kind IN ('temporary', 'permanent')", name=op.f("ck_ip_blocks_ip_block_kind")
        ),
        sa.ForeignKeyConstraint(
            ["created_by"],
            ["users.id"],
            name=op.f("fk_ip_blocks_created_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ip_blocks")),
    )
    op.create_index("ix_ip_blocks_active", "ip_blocks", ["removed_at", "expires_at"], unique=False)
    op.create_index(op.f("ix_ip_blocks_network"), "ip_blocks", ["network"], unique=False)
    op.create_table(
        "platform_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("changed_by", sa.Uuid(), nullable=True),
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
            ["changed_by"],
            ["users.id"],
            name=op.f("fk_platform_settings_changed_by_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_platform_settings")),
    )


def downgrade() -> None:
    op.drop_table("platform_settings")
    op.drop_index(op.f("ix_ip_blocks_network"), table_name="ip_blocks")
    op.drop_index("ix_ip_blocks_active", table_name="ip_blocks")
    op.drop_table("ip_blocks")
