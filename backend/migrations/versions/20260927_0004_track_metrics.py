"""Add track_metrics — derived metrics per track.

Hand-written so constraint and index names match the model exactly: CI compares
the migrated schema against 'Base.metadata' and fails on any drift.

Revision ID: 20260927_0004
Revises: 20260926_0003
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260927_0004"
down_revision: str | None = "20260926_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "track_metrics",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("space", sa.String(length=16), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=False),
        sa.Column("availability", sa.String(length=16), nullable=False),
        sa.Column("value", sa.Float(), nullable=True),
        sa.Column("sample_count", sa.Integer(), nullable=False),
        sa.Column("definition_version", sa.String(length=32), nullable=False),
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
            "track_id >= 0",
            name="ck_track_metrics_track_metric_track_non_negative",
        ),
        sa.CheckConstraint(
            "sample_count >= 0",
            name="ck_track_metrics_track_metric_sample_count_non_negative",
        ),
        sa.CheckConstraint(
            "(availability = 'available' AND value IS NOT NULL) "
            "OR (availability = 'unavailable' AND value IS NULL)",
            name="ck_track_metrics_track_metric_availability_matches_value",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_track_metrics_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name="fk_track_metrics_analysis_run_id_analysis_runs",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_track_metrics"),
        sa.UniqueConstraint(
            "analysis_run_id",
            "track_id",
            "metric_name",
            name="uq_track_metric_run_track_name",
        ),
    )
    op.create_index("ix_track_metrics_organization_id", "track_metrics", ["organization_id"])
    op.create_index("ix_track_metrics_analysis_run_id", "track_metrics", ["analysis_run_id"])
    op.create_index("ix_track_metrics_run_track", "track_metrics", ["analysis_run_id", "track_id"])


def downgrade() -> None:
    op.drop_table("track_metrics")
