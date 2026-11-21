import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.phone import normalize_phone
from app.models.enums import Language, UserRole
from app.schemas.common import ORMModel


class ProfileOut(ORMModel):
    id: uuid.UUID
    email: str | None
    first_name: str | None
    last_name: str | None
    display_name: str | None
    phone: str | None
    whatsapp: str | None
    avatar_url: str | None
    preferred_language: Language
    role: UserRole
    city: str | None
    zip_code: str | None
    whatsapp_opt_in: bool
    created_at: datetime


class PublicProfileOut(ORMModel):
    """What other users may see about a seller."""

    id: uuid.UUID
    display_name: str | None
    avatar_url: str | None
    city: str | None


class AdminProfileOut(ProfileOut):
    """What an admin sees in the member list."""

    is_banned: bool


class AdminProfileUpdate(BaseModel):
    role: UserRole | None = None
    is_banned: bool | None = None


class ProfileUpdate(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=60)
    last_name: str | None = Field(default=None, min_length=1, max_length=60)
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_language: Language | None = None
    phone: str | None = Field(default=None, max_length=32)
    whatsapp: str | None = Field(default=None, max_length=32)
    whatsapp_opt_in: bool | None = None
    city: str | None = Field(default=None, max_length=80)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")

    @field_validator("phone", "whatsapp")
    @classmethod
    def _international(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None  # clears the number
        phone = normalize_phone(value)
        if phone is None:
            raise ValueError("Enter a phone number with its country code, like +1 703 555 0123")
        return phone
