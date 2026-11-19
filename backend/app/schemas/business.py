import re
import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.enums import DirectoryStatus, EntryKind
from app.schemas.category import CategoryOut

# Languages a business or helper can say they speak (ISO 639-1).
LANGUAGE_CODES = ("en", "te", "hi", "ta", "kn", "ml", "mr", "gu", "bn", "ur", "pa")
MAX_MENU_ITEMS = 300
MAX_MENU_PRICE_CENTS = 1_000_000  # $10,000 sanity cap per dish

_PHONE_ALLOWED = re.compile(r"^[0-9+()\-.\s]{7,32}$")
# A US/Canada number people can call: 10 digits (optional leading 1), area code and exchange
# not starting with 0 or 1. Rules out blanks, "000-000-0000" and registry filler.
CALLABLE_PHONE = r"^1?[2-9][0-9]{2}[2-9][0-9]{6}$"


def is_callable_phone(value: str | None) -> bool:
    return bool(re.match(CALLABLE_PHONE, re.sub(r"\D", "", value or "")))


def _normalize_phone(value: str | None) -> str | None:
    """Keep what people type ("(703) 555-0100") but reject anything that isn't a phone number."""
    if value is None or not value.strip():
        return None
    value = " ".join(value.split())
    if not _PHONE_ALLOWED.match(value) or sum(c.isdigit() for c in value) < 7:
        raise ValueError("Enter a valid phone number")
    return value


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


class BusinessBase(BaseModel):
    category_id: int | None = None
    name: str | None = Field(default=None, min_length=2, max_length=120)
    name_te: str | None = Field(default=None, max_length=240)
    description_en: str | None = Field(default=None, max_length=3000)
    description_te: str | None = Field(default=None, max_length=6000)
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = Field(default=None, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    website: str | None = Field(default=None, max_length=500)
    address: str | None = Field(default=None, max_length=200)
    city: str | None = Field(default=None, max_length=80)
    zip_code: str | None = Field(default=None, pattern=r"^\d{5}(-\d{4})?$")
    service_area: str | None = Field(default=None, max_length=200)
    hours: str | None = Field(default=None, max_length=200)
    languages: list[str] | None = None

    @field_validator(
        "name",
        "name_te",
        "description_en",
        "description_te",
        "email",
        "website",
        "address",
        "city",
        "zip_code",
        "service_area",
        "hours",
        mode="before",
    )
    @classmethod
    def _strip(cls, v: object) -> object:
        return _clean(v) if isinstance(v, str) else v

    @field_validator("phone")
    @classmethod
    def _phone(cls, v: str | None) -> str | None:
        v = _normalize_phone(v)
        if v is not None and not is_callable_phone(v):
            raise ValueError("Enter a 10-digit US phone number, like 703-555-0123")
        return v

    @field_validator("whatsapp")
    @classmethod
    def _whatsapp(cls, v: str | None) -> str | None:
        return _normalize_phone(v)  # may be an international number

    @field_validator("website")
    @classmethod
    def _website(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if not re.match(r"^https?://", v, re.I):
            v = f"https://{v}"
        if not re.match(r"^https?://[^\s/$.?#][^\s]*\.[^\s]+$", v, re.I):
            raise ValueError("Enter a valid website address")
        return v

    @field_validator("languages")
    @classmethod
    def _languages(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        out = []
        for code in v:
            code = code.strip().lower()
            if code not in LANGUAGE_CODES:
                raise ValueError(f"Unknown language code: {code}")
            if code not in out:
                out.append(code)
        return out


class BusinessCreate(BusinessBase):
    kind: EntryKind
    name: str = Field(min_length=2, max_length=120)
    # Required when adding an individual: they agreed to be listed with these contact details.
    consent_confirmed: bool = False

    @model_validator(mode="after")
    def _check(self) -> "BusinessCreate":
        # Only entries people can call are listed, so a phone number is required.
        if not self.phone:
            raise ValueError("Add a phone number customers can call")
        if self.kind == EntryKind.INDIVIDUAL:
            if not self.consent_confirmed:
                raise ValueError("Confirm this person agreed to be listed")
            self.address = None  # never publish a helper's home address
        return self


class BusinessUpdate(BusinessBase):
    @model_validator(mode="after")
    def _keep_phone(self) -> "BusinessUpdate":
        if "phone" in self.model_fields_set and not self.phone:
            raise ValueError("Add a phone number customers can call")
        return self


class BusinessReview(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=500)
    is_verified: bool | None = None


class MenuItemIn(BaseModel):
    section: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=160)
    name_te: str | None = Field(default=None, max_length=240)
    description: str | None = Field(default=None, max_length=500)
    price_cents: int | None = Field(default=None, ge=0, le=MAX_MENU_PRICE_CENTS)
    is_vegetarian: bool | None = None

    @field_validator("section", "name", "name_te", "description", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return _clean(v) if isinstance(v, str) else v


class MenuReplace(BaseModel):
    items: list[MenuItemIn] = Field(max_length=MAX_MENU_ITEMS)


class MenuItemOut(MenuItemIn):
    id: uuid.UUID | None = None  # None for AI suggestions that aren't saved yet


class MenuSuggestion(BaseModel):
    """What the AI read from menu photos; the editor reviews it before saving."""

    items: list[MenuItemOut]


class BusinessOut(BaseModel):
    id: uuid.UUID
    kind: EntryKind
    status: DirectoryStatus
    name: str
    name_te: str | None
    description_en: str | None
    description_te: str | None
    phone: str | None
    whatsapp: str | None
    email: str | None
    website: str | None
    address: str | None
    city: str | None
    zip_code: str | None
    service_area: str | None
    hours: str | None
    languages: list[str]
    is_verified: bool
    # Imported from public data: "npi" = NPI Registry, "osm" = OpenStreetMap; null = a person.
    source: str | None = None
    # Where the imported record lives (OpenStreetMap entries link back for attribution).
    source_url: str | None = None
    # Imported entries: "Endocrinologist", "Indian, Biryani · Restaurant" (English).
    specialty: str | None = None
    category: CategoryOut | None
    menu: list[MenuItemOut]
    # True when an individual's contact details are withheld from a signed-out visitor.
    contact_hidden: bool = False
    # Only for the submitter and staff.
    can_edit: bool = False
    review_note: str | None = None
    created_at: datetime
    updated_at: datetime
