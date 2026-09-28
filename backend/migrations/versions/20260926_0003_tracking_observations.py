"""Add tracking_observations — per-frame tracked objects in pixel space.

Hand-written so constraint and index names match the model exactly: CI compares
the migrated schema against 'Base.metadata' and fails on any drift.

Revision ID: 20260926_0003
Revises: 20260926_0002
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260926_0003"
down_revision: str | None = "20260926_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tracking_observations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("analysis_run_id", sa.Uuid(), nullable=False),
        sa.Column("video_id", sa.Uuid(), nullable=False),
        sa.Column("frame_index", sa.Integer(), nullable=False),
        sa.Column("timestamp_seconds", sa.Float(), nullable=False),
        sa.Column("track_id", sa.Integer(), nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("x2", sa.Float(), nullable=False),
        sa.Column("y2", sa.Float(), nullable=False),
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
            "confidence >= 0 AND confidence <= 1",
            name="ck_tracking_observations_observation_confidence_range",
        ),
        sa.CheckConstraint(
            "frame_index >= 0",
            name="ck_tracking_observations_observation_frame_non_negative",
        ),
        sa.CheckConstraint(
            "timestamp_seconds >= 0",
            name="ck_tracking_observations_observation_timestamp_non_negative",
        ),
        sa.CheckConstraint(
            "x2 >= x1 AND y2 >= y1",
            name="ck_tracking_observations_observation_bbox_ordered",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name="fk_tracking_observations_organization_id_organizations",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dataset_id"],
            ["tracking_datasets.id"],
            name="fk_tracking_observations_dataset_id_tracking_datasets",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["analysis_run_id"],
            ["analysis_runs.id"],
            name="fk_tracking_observations_analysis_run_id_analysis_runs",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["video_id"],
            ["videos.id"],
            name="fk_tracking_observations_video_id_videos",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_tracking_observations"),
    )
    op.create_index(
        "ix_tracking_observations_organization_id", "tracking_observations", ["organization_id"]
    )
    op.create_index("ix_tracking_observations_dataset_id", "tracking_observations", ["dataset_id"])
    op.create_index(
        "ix_tracking_observations_analysis_run_id", "tracking_observations", ["analysis_run_id"]
    )
    op.create_index("ix_tracking_observations_video_id", "tracking_observations", ["video_id"])
    op.create_index(
        "ix_tracking_obs_dataset_frame",
        "tracking_observations",
        ["dataset_id", "frame_index"],
    )
    op.create_index(
        "ix_tracking_obs_dataset_track",
        "tracking_observations",
        ["dataset_id", "track_id"],
    )
    op.create_index(
        "ix_tracking_obs_run_frame",
        "tracking_observations",
        ["analysis_run_id", "frame_index"],
    )
    op.create_index("ix_tracking_obs_video", "tracking_observations", ["video_id"])


def downgrade() -> None:
    op.drop_table("tracking_observations")
