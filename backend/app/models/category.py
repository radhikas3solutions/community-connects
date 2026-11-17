from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import CategoryKind, str_enum


class Category(TimestampMixin, Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    kind: Mapped[CategoryKind] = mapped_column(str_enum(CategoryKind, "category_kind"), index=True)
    name_en: Mapped[str] = mapped_column(String(80))
    name_te: Mapped[str] = mapped_column(String(120))
    icon: Mapped[str | None] = mapped_column(String(16))  # emoji for now; swap for icon keys later
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"))
    # Highlights Indian / Telugu community-specific categories in the UI
    is_community_specific: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
