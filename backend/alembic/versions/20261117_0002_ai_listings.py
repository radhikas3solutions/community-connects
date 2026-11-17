"""AI listings: listing photos, AI usage log, full-text + trigram search

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english', coalesce(title_en, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description_en, '')), 'B')"
)
TRGM_COLUMNS = ("title_en", "title_te", "description_te")


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    op.create_table(
        "listing_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("storage_path", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(32), nullable=False),
        sa.Column("width", sa.Integer, nullable=False),
        sa.Column("height", sa.Integer, nullable=False),
        sa.Column("size_bytes", sa.Integer, nullable=False),
        sa.Column("position", sa.Integer, server_default="0", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            ondelete="CASCADE",
            name="fk_listing_images_listing_id_listings",
        ),
        sa.UniqueConstraint("storage_path", name="uq_listing_images_storage_path"),
    )
    op.create_index("ix_listing_images_listing_id", "listing_images", ["listing_id"])

    op.create_table(
        "ai_usage",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feature", sa.String(32), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("model", sa.String(64)),
        sa.Column("request_id", sa.String(128)),
        sa.Column("input_tokens", sa.Integer, server_default="0", nullable=False),
        sa.Column("output_tokens", sa.Integer, server_default="0", nullable=False),
        sa.Column("cache_read_tokens", sa.Integer, server_default="0", nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6)),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["profiles.id"],
            ondelete="CASCADE",
            name="fk_ai_usage_profile_id_profiles",
        ),
        sa.ForeignKeyConstraint(
            ["listing_id"],
            ["listings.id"],
            ondelete="SET NULL",
            name="fk_ai_usage_listing_id_listings",
        ),
    )
    op.create_index("ix_ai_usage_profile_created", "ai_usage", ["profile_id", "created_at"])

    op.add_column("listings", sa.Column("ai_price_low_cents", sa.Integer))
    op.add_column("listings", sa.Column("ai_price_high_cents", sa.Integer))
    op.add_column(
        "listings",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR,
            sa.Computed(SEARCH_VECTOR_SQL, persisted=True),
        ),
    )
    op.create_index(
        "ix_listings_search_vector", "listings", ["search_vector"], postgresql_using="gin"
    )
    for col in TRGM_COLUMNS:
        op.create_index(
            f"ix_listings_{col}_trgm",
            "listings",
            [col],
            postgresql_using="gin",
            postgresql_ops={col: "gin_trgm_ops"},
        )


def downgrade() -> None:
    for col in TRGM_COLUMNS:
        op.drop_index(f"ix_listings_{col}_trgm", table_name="listings")
    op.drop_index("ix_listings_search_vector", table_name="listings")
    op.drop_column("listings", "search_vector")
    op.drop_column("listings", "ai_price_high_cents")
    op.drop_column("listings", "ai_price_low_cents")
    op.drop_table("ai_usage")
    op.drop_table("listing_images")
    # pg_trgm extension intentionally left installed.
