"""Directory: businesses and individuals offering services, restaurant menus

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BUSINESS_SEARCH_SQL = (
    "setweight(to_tsvector('english', coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description_en, '')), 'B') || "
    "setweight(to_tsvector('english', coalesce(service_area, '')), 'C')"
)
TRGM_COLUMNS = ("name", "name_te")


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


def upgrade() -> None:
    op.create_table(
        "businesses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), server_default="pending_review", nullable=False),
        sa.Column("category_id", sa.Integer),
        sa.Column("submitted_by_id", postgresql.UUID(as_uuid=True)),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("name_te", sa.String(240)),
        sa.Column("description_en", sa.Text),
        sa.Column("description_te", sa.Text),
        sa.Column("phone", sa.String(32)),
        sa.Column("whatsapp", sa.String(32)),
        sa.Column("email", sa.String(320)),
        sa.Column("website", sa.String(500)),
        sa.Column("address", sa.String(200)),
        sa.Column("city", sa.String(80)),
        sa.Column("zip_code", sa.String(10)),
        sa.Column("service_area", sa.String(200)),
        sa.Column("hours", sa.String(200)),
        sa.Column("languages", postgresql.ARRAY(sa.String(8)), server_default="{}", nullable=False),
        sa.Column("consent_confirmed", sa.Boolean, server_default="false", nullable=False),
        sa.Column("is_verified", sa.Boolean, server_default="false", nullable=False),
        sa.Column("review_note", sa.String(500)),
        sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column(
            "search_vector", postgresql.TSVECTOR, sa.Computed(BUSINESS_SEARCH_SQL, persisted=True)
        ),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["category_id"],
            ["categories.id"],
            ondelete="SET NULL",
            name="fk_businesses_category_id_categories",
        ),
        sa.ForeignKeyConstraint(
            ["submitted_by_id"],
            ["profiles.id"],
            ondelete="SET NULL",
            name="fk_businesses_submitted_by_id_profiles",
        ),
        sa.CheckConstraint(
            _enum_check("kind", ["business", "individual"]), name=op.f("ck_businesses_entry_kind")
        ),
        sa.CheckConstraint(
            _enum_check("status", ["pending_review", "active", "rejected", "removed"]),
            name=op.f("ck_businesses_directory_status"),
        ),
    )
    op.create_index("ix_businesses_category_id", "businesses", ["category_id"])
    op.create_index("ix_businesses_submitted_by_id", "businesses", ["submitted_by_id"])
    op.create_index("ix_businesses_status_name", "businesses", ["status", "name"])
    op.create_index(
        "ix_businesses_search_vector", "businesses", ["search_vector"], postgresql_using="gin"
    )
    for col in TRGM_COLUMNS:
        op.create_index(
            f"ix_businesses_{col}_trgm",
            "businesses",
            [col],
            postgresql_using="gin",
            postgresql_ops={col: "gin_trgm_ops"},
        )

    op.create_table(
        "menu_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("business_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(80)),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("name_te", sa.String(240)),
        sa.Column("description", sa.String(500)),
        sa.Column("price_cents", sa.Integer),
        sa.Column("is_vegetarian", sa.Boolean),
        sa.Column("position", sa.Integer, server_default="0", nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(
            ["business_id"],
            ["businesses.id"],
            ondelete="CASCADE",
            name="fk_menu_items_business_id_businesses",
        ),
        sa.CheckConstraint(
            "price_cents IS NULL OR price_cents >= 0", name=op.f("ck_menu_items_price_non_negative")
        ),
    )
    op.create_index("ix_menu_items_business_id", "menu_items", ["business_id"])

    # AI usage rows can now come from menu reading as well as listing drafts.
    op.add_column("ai_usage", sa.Column("business_id", postgresql.UUID(as_uuid=True)))
    op.create_foreign_key(
        "fk_ai_usage_business_id_businesses",
        "ai_usage",
        "businesses",
        ["business_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_ai_usage_business_id_businesses", "ai_usage", type_="foreignkey")
    op.drop_column("ai_usage", "business_id")
    op.drop_table("menu_items")
    op.drop_table("businesses")
