"""Add report provenance — the analysis run and definition version.

Hand-written so constraint and index names match the model exactly: CI compares
the migrated schema against 'Base.metadata' and fails on any drift.

Revision ID: 20260930_0005
Revises: 20260927_0004
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260930_0005"
down_revision: str | None = "20260927_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reports", sa.Column("analysis_run_id", sa.Uuid(), nullable=True))
    op.add_column(
        "reports",
        sa.Column("definition_version", sa.String(length=32), server_default="v1", nullable=False),
    )
    op.create_foreign_key(
        "fk_reports_analysis_run_id_analysis_runs",
        "reports",
        "analysis_runs",
        ["analysis_run_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_reports_analysis_run_id", "reports", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_reports_analysis_run_id", table_name="reports")
    op.drop_constraint("fk_reports_analysis_run_id_analysis_runs", "reports", type_="foreignkey")
    op.drop_column("reports", "definition_version")
    op.drop_column("reports", "analysis_run_id")
