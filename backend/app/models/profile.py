import uuid

from geoalchemy2 import Geography
from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin
from app.models.enums import Language, UserRole, str_enum


class Profile(TimestampMixin, Base):
    """App-level user record. `id` equals the Supabase `auth.users.id` (JWT `sub`)."""

    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    email: Mapped[str | None] = mapped_column(String(320), index=True)
    first_name: Mapped[str | None] = mapped_column(String(60))
    last_name: Mapped[str | None] = mapped_column(String(60))
    display_name: Mapped[str | None] = mapped_column(String(80))
    avatar_url: Mapped[str | None] = mapped_column(String(1024))
    phone: Mapped[str | None] = mapped_column(String(32))  # international format, "+17035550123"
    whatsapp: Mapped[str | None] = mapped_column(String(32))
    whatsapp_opt_in: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    preferred_language: Mapped[Language] = mapped_column(
        str_enum(Language, "language"), default=Language.EN, server_default=Language.EN.value
    )
    role: Mapped[UserRole] = mapped_column(
        str_enum(UserRole, "user_role"), default=UserRole.USER, server_default=UserRole.USER.value
    )
    city: Mapped[str | None] = mapped_column(String(80))
    zip_code: Mapped[str | None] = mapped_column(String(10))
    location = mapped_column(Geography(geometry_type="POINT", srid=4326), nullable=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
