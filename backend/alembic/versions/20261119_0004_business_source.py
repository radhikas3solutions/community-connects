"""Directory entries imported from public datasets (NPI Registry)

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("businesses", sa.Column("source", sa.String(20), nullable=True))
    op.add_column("businesses", sa.Column("external_id", sa.String(64), nullable=True))
    op.add_column(
        "businesses",
        sa.Column("source_data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.create_index(
        "uq_businesses_source_external_id",
        "businesses",
        ["source", "external_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("uq_businesses_source_external_id", table_name="businesses")
    op.drop_column("businesses", "source_data")
    op.drop_column("businesses", "external_id")
    op.drop_column("businesses", "source")
