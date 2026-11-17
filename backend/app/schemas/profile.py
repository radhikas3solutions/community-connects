import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import Language, UserRole
from app.schemas.common import ORMModel


class ProfileOut(ORMModel):
    id: uuid.UUID
    email: str | None
    display_name: str | None
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


class ProfileUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_language: Language | None = None
    phone: str | None = Field(default=None, max_length=32, pattern=r"^\+?[0-9 ()\-]{7,32}$")
    whatsapp_opt_in: bool | None = None
    city: str | None = Field(default=None, max_length=80)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
