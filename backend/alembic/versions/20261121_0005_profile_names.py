"""First and last name and WhatsApp number on profiles (collected at registration)

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("profiles", sa.Column("first_name", sa.String(60), nullable=True))
    op.add_column("profiles", sa.Column("last_name", sa.String(60), nullable=True))
    op.add_column("profiles", sa.Column("whatsapp", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_column("profiles", "whatsapp")
    op.drop_column("profiles", "last_name")
    op.drop_column("profiles", "first_name")
