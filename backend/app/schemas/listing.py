import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.models.enums import ItemCondition, Language, ListingStatus, ListingType
from app.schemas.category import CategoryOut
from app.schemas.common import GeoPoint, ORMModel
from app.schemas.profile import PublicProfileOut

MAX_PRICE_CENTS = 10_000_000_00  # $10M sanity cap


class ListingBase(BaseModel):
    category_id: int | None = None
    condition: ItemCondition | None = None
    title_en: str | None = Field(default=None, min_length=3, max_length=140)
    title_te: str | None = Field(default=None, min_length=2, max_length=280)
    description_en: str | None = Field(default=None, max_length=5000)
    description_te: str | None = Field(default=None, max_length=10000)
    price_cents: int | None = Field(default=None, ge=0, le=MAX_PRICE_CENTS)
    is_negotiable: bool = False
    city: str | None = Field(default=None, max_length=80)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    location: GeoPoint | None = None


class ListingCreate(ListingBase):
    listing_type: ListingType
    source_language: Language = Language.EN

    @model_validator(mode="after")
    def _check(self) -> "ListingCreate":
        if not (self.title_en or self.title_te):
            raise ValueError("A title in English or Telugu is required")
        if self.listing_type == ListingType.FREE:
            if self.price_cents not in (None, 0):
                raise ValueError("Free listings cannot have a price")
            self.price_cents = 0
        elif self.listing_type == ListingType.SELL and self.price_cents is None:
            raise ValueError("Items for sale need a price")
        return self


class ListingUpdate(ListingBase):
    # Owners may only move between these; moderation states are set by staff.
    status: ListingStatus | None = None

    @model_validator(mode="after")
    def _check_status(self) -> "ListingUpdate":
        allowed = {ListingStatus.DRAFT, ListingStatus.ACTIVE, ListingStatus.SOLD}
        if self.status is not None and self.status not in allowed:
            raise ValueError(f"status must be one of {sorted(s.value for s in allowed)}")
        return self


class ListingOut(ORMModel):
    id: uuid.UUID
    listing_type: ListingType
    status: ListingStatus
    condition: ItemCondition | None
    source_language: Language
    title_en: str | None
    title_te: str | None
    description_en: str | None
    description_te: str | None
    price_cents: int | None
    currency: str
    is_negotiable: bool
    city: str | None
    zip_code: str | None
    # Populated from the query's lat/lng columns, not from the raw PostGIS value on the model.
    location: GeoPoint | None = Field(default=None, validation_alias="_computed_location")
    distance_km: float | None = None
    category: CategoryOut | None
    owner: PublicProfileOut
    created_at: datetime
    updated_at: datetime
