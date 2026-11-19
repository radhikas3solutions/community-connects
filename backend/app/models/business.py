import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin
from app.models.category import Category
from app.models.enums import DirectoryStatus, EntryKind, str_enum

BUSINESS_SEARCH_SQL = (
    "setweight(to_tsvector('english', coalesce(name, '')), 'A') || "
    "setweight(to_tsvector('english', coalesce(description_en, '')), 'B') || "
    "setweight(to_tsvector('english', coalesce(service_area, '')), 'C')"
)


class MenuItem(TimestampMixin, Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        CheckConstraint("price_cents IS NULL OR price_cents >= 0", name="price_non_negative"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), index=True
    )
    section: Mapped[str | None] = mapped_column(String(80))  # "Biryanis", "Tiffins"
    name: Mapped[str] = mapped_column(String(160))  # as printed on the menu
    name_te: Mapped[str | None] = mapped_column(String(240))
    description: Mapped[str | None] = mapped_column(String(500))
    price_cents: Mapped[int | None] = mapped_column(Integer)
    is_vegetarian: Mapped[bool | None] = mapped_column(Boolean)
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")


class Business(TimestampMixin, Base):
    """A directory entry: a business, or an individual offering a service (helper, tutor)."""

    __tablename__ = "businesses"
    __table_args__ = (
        Index("ix_businesses_status_name", "status", "name"),
        Index("ix_businesses_search_vector", "search_vector", postgresql_using="gin"),
        Index("uq_businesses_source_external_id", "source", "external_id", unique=True),
        *(
            Index(
                f"ix_businesses_{col}_trgm",
                col,
                postgresql_using="gin",
                postgresql_ops={col: "gin_trgm_ops"},
            )
            for col in ("name", "name_te")
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    kind: Mapped[EntryKind] = mapped_column(str_enum(EntryKind, "entry_kind"))
    status: Mapped[DirectoryStatus] = mapped_column(
        str_enum(DirectoryStatus, "directory_status"),
        default=DirectoryStatus.PENDING_REVIEW,
        server_default=DirectoryStatus.PENDING_REVIEW.value,
    )
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("categories.id", ondelete="SET NULL"), index=True
    )
    # Who added it (and may edit it). Ownership claims by the actual business come later.
    submitted_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("profiles.id", ondelete="SET NULL"), index=True
    )

    name: Mapped[str] = mapped_column(String(120))  # as the business writes it
    name_te: Mapped[str | None] = mapped_column(String(240))
    description_en: Mapped[str | None] = mapped_column(Text)
    description_te: Mapped[str | None] = mapped_column(Text)

    phone: Mapped[str | None] = mapped_column(String(32))
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    email: Mapped[str | None] = mapped_column(String(320))
    website: Mapped[str | None] = mapped_column(String(500))

    # Street address only for businesses; individuals give just a city / service area.
    address: Mapped[str | None] = mapped_column(String(200))
    city: Mapped[str | None] = mapped_column(String(80))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    service_area: Mapped[str | None] = mapped_column(String(200))  # "Ashburn, Sterling, Herndon"
    hours: Mapped[str | None] = mapped_column(String(200))  # free text: "Mon-Sat 11am-10pm"
    languages: Mapped[list[str]] = mapped_column(
        ARRAY(String(8)), default=list, server_default="{}"
    )

    # Someone adding a helper or tutor confirmed that person agreed to be listed.
    consent_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    review_note: Mapped[str | None] = mapped_column(String(500))  # moderator's reason on reject
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Imported from a public dataset ("npi" = the NPI Registry); null = added by a person.
    source: Mapped[str | None] = mapped_column(String(20))
    external_id: Mapped[str | None] = mapped_column(String(64))
    # What the import knew (provider names, NPI numbers, specialties), to merge re-imports.
    source_data: Mapped[dict | None] = mapped_column(JSONB)

    search_vector = mapped_column(TSVECTOR, Computed(BUSINESS_SEARCH_SQL, persisted=True))

    category: Mapped[Category | None] = relationship(lazy="joined")
    menu: Mapped[list[MenuItem]] = relationship(
        lazy="selectin",
        order_by=MenuItem.position,
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
