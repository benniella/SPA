"""Session MFA assurance.

Administrative authorization requires that the current session has satisfied a
second factor. The column is additive: an ordinary session leaves it NULL and
behaves exactly as before.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1db7fc570c3"
down_revision: str | None = "1c0d52218720"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sessions",
        sa.Column("mfa_verified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sessions", "mfa_verified_at")
