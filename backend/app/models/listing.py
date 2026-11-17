import uuid
from decimal import Decimal

from geoalchemy2 import Geography
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.category import Category
from app.models.enums import ItemCondition, Language, ListingStatus, ListingType, str_enum
from app.models.profile import Profile


class Listing(TimestampMixin, Base):
    __tablename__ = "listings"
    __table_args__ = (
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_non_negative"),
        CheckConstraint(
            "listing_type <> 'free' OR COALESCE(price_cents, 0) = 0", name="free_has_no_price"
        ),
        CheckConstraint("title_en IS NOT NULL OR title_te IS NOT NULL", name="has_title"),
        Index("ix_listings_status_created", "status", "created_at"),
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

    # Filled by AI in Phase 2 (0-1 score); kept here so the schema is stable.
    ai_confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))

    owner: Mapped[Profile] = relationship(lazy="joined")
    category: Mapped[Category | None] = relationship(lazy="joined")
