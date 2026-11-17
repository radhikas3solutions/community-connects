"""Initial schema: PostGIS, profiles, categories, listings

Revision ID: 0001
Revises:
Create Date: 2026-11-17
"""

from collections.abc import Sequence

import geoalchemy2
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _enum_check(column: str, values: list[str]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def _point(name: str = "location") -> sa.Column:
    return sa.Column(
        name,
        geoalchemy2.Geography(geometry_type="POINT", srid=4326, spatial_index=False),
        nullable=True,
    )


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("display_name", sa.String(80)),
        sa.Column("avatar_url", sa.String(1024)),
        sa.Column("phone", sa.String(32)),
        sa.Column("whatsapp_opt_in", sa.Boolean, server_default="false", nullable=False),
        sa.Column("preferred_language", sa.String(32), server_default="en", nullable=False),
        sa.Column("role", sa.String(32), server_default="user", nullable=False),
        sa.Column("city", sa.String(80)),
        sa.Column("zip_code", sa.String(10)),
        _point(),
        sa.Column("is_banned", sa.Boolean, server_default="false", nullable=False),
        *_timestamps(),
        sa.PrimaryKeyConstraint("id", name="pk_profiles"),
        sa.CheckConstraint(
            _enum_check("preferred_language", ["en", "te"]), name=op.f("ck_profiles_language")
        ),
        sa.CheckConstraint(
            _enum_check("role", ["user", "business", "moderator", "admin"]),
            name=op.f("ck_profiles_user_role"),
        ),
    )
    op.create_index("ix_profiles_email", "profiles", ["email"])
    op.create_index("idx_profiles_location", "profiles", ["location"], postgresql_using="gist")

    op.create_table(
        "categories",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name_en", sa.String(80), nullable=False),
        sa.Column("name_te", sa.String(120), nullable=False),
        sa.Column("icon", sa.String(16)),
        sa.Column("parent_id", sa.Integer),
        sa.Column("is_community_specific", sa.Boolean, server_default="false", nullable=False),
        sa.Column("sort_order", sa.Integer, server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["parent_id"],
            ["categories.id"],
            ondelete="SET NULL",
            name="fk_categories_parent_id_categories",
        ),
        sa.CheckConstraint(
            _enum_check("kind", ["marketplace", "business", "community"]),
            name=op.f("ck_categories_category_kind"),
        ),
    )
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)
    op.create_index("ix_categories_kind", "categories", ["kind"])

    op.create_table(
        "listings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("listing_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("condition", sa.String(32)),
        sa.Column("source_language", sa.String(32), server_default="en", nullable=False),
        sa.Column("title_en", sa.String(140)),
        sa.Column("title_te", sa.String(280)),
        sa.Column("description_en", sa.Text),
        sa.Column("description_te", sa.Text),
        sa.Column("price_cents", sa.Integer),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("is_negotiable", sa.Boolean, server_default="false", nullable=False),
        sa.Column("city", sa.String(80)),
        sa.Column("zip_code", sa.String(10)),
        _point(),
        sa.Column("ai_confidence", sa.Numeric(4, 3)),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["profiles.id"], ondelete="CASCADE", name="fk_listings_owner_id_profiles"
        ),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="SET NULL",
            name="fk_listings_category_id_categories",
        ),
        sa.CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0", name=op.f("ck_listings_price_non_negative")
        ),
        sa.CheckConstraint(
            "listing_type <> 'free' OR COALESCE(price_cents, 0) = 0",
            name=op.f("ck_listings_free_has_no_price"),
        ),
        sa.CheckConstraint(
            "title_en IS NOT NULL OR title_te IS NOT NULL", name=op.f("ck_listings_has_title")
        ),
        sa.CheckConstraint(
            _enum_check("listing_type", ["sell", "buy", "free"]),
            name=op.f("ck_listings_listing_type"),
        ),
        sa.CheckConstraint(
            _enum_check("status", ["draft", "pending_review", "active", "sold", "removed"]),
            name=op.f("ck_listings_listing_status"),
        ),
        sa.CheckConstraint(
            "condition IS NULL OR "
            + _enum_check("condition", ["new", "like_new", "good", "fair", "for_parts"]),
            name=op.f("ck_listings_item_condition"),
        ),
        sa.CheckConstraint(
            _enum_check("source_language", ["en", "te"]), name=op.f("ck_listings_language")
        ),
    )
    op.create_index("ix_listings_owner_id", "listings", ["owner_id"])
    op.create_index("ix_listings_category_id", "listings", ["category_id"])
    op.create_index("ix_listings_status_created", "listings", ["status", "created_at"])
    op.create_index("idx_listings_location", "listings", ["location"], postgresql_using="gist")


def downgrade() -> None:
    op.drop_table("listings")
    op.drop_table("categories")
    op.drop_table("profiles")
    # PostGIS extension intentionally left installed.
