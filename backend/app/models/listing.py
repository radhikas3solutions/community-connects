import uuid
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import (
    CheckConstraint,
    Computed,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.category import Category
from app.models.enums import ItemCondition, Language, ListingStatus, ListingType, str_enum
from app.models.listing_image import ListingImage
from app.models.profile import Profile

# English full-text search document (title weighted above description). Telugu has no
# built-in Postgres stemmer, so Telugu text is searched with trigram indexes instead.
SEARCH_VECTOR_SQL = (
    "setweight(to_tsvector('english', coalesce(title_en, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description_en, '')), 'B')"
)


class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_non_negative"),
        CheckConstraint(
            "listing_type <> 'free' OR COALESCE(price_cents, 0) = 0", name="free_has_no_price"
        ),
        CheckConstraint("title_en IS NOT NULL OR title_te IS NOT NULL", name="has_title"),
        Index("ix_listings_status_created", "status", "created_at"),
        Index("ix_listings_search_vector", "search_vector", postgresql_using="gin"),
        *(
            Index(
                f"ix_listings_{col}_trgm",
                col,
                postgresql_using="gin",
                postgresql_ops={col: "gin_trgm_ops"},
            )
            for col in ("title_en", "title_te", "description_te")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    owner_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("profiles.id", ondelete="CASCADE"), index=True
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    listing_type: Mapped[ListingType] = mapped_column(str_enum(ListingType, "listing_type"))
    status: Mapped[ListingStatus] = mapped_column(
        str_enum(ListingStatus, "listing_status"),
        default=ListingStatus.ACTIVE,
        server_default=ListingStatus.ACTIVE.value,
    )
    condition: Mapped[ItemCondition | None] = mapped_column(
        str_enum(ItemCondition, "item_condition")
    )

    # Bilingual content. The source language is what the seller wrote (or the AI drafted);
    # the other language is a translation (Phase 2 fills it in automatically).
    source_language: Mapped[Language] = mapped_column(
        str_enum(Language, "language"), default=Language.EN, server_default=Language.EN.value
    )
    title_en: Mapped[str | None] = mapped_column(String(140))
    title_te: Mapped[str | None] = mapped_column(String(280))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_te: Mapped[str | None] = mapped_column(Text)

    price_cents: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3), default="USD", server_default="USD")
    is_negotiable: Mapped[bool] = mapped_column(default=False, server_default="false")

    city: Mapped[str | None] = mapped_column(String(80))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    # Approximate (privacy-fuzzed) pickup location; GIST index created in migration.
    location = mapped_column(Geography(geometry_type="POINT", srid=4326, spatial_index=True))

    # Set when Claude drafted the listing (0-1 self-reported confidence), with its price range.
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    ai_price_low_cents: Mapped[int | None] = mapped_column(Integer)
    ai_price_high_cents: Mapped[int | None] = mapped_column(Integer)

    search_vector = mapped_column(TSVECTOR, Computed(SEARCH_VECTOR_SQL, persisted=True))

    owner: Mapped[Profile] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
    images: Mapped[list[ListingImage]] = relationship(
        lazy="selectin",
        order_by=ListingImage.position,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
