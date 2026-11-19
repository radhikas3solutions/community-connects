"""Staff-only imports of public data into the directory.

OpenStreetMap: restaurants, fast food and cafés, one request per area (see services/osm.py).

NPI Registry: one request = one ZIP code x one kind of provider, so the admin page can
show progress and no request runs long. Imported entries go live unverified and are
labelled as coming from public records. Re-running an import updates entries instead
of duplicating them, and never brings back an entry a moderator removed or rejected.
"""

import logging
from collections import Counter

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_npi_client, get_osm_client, require_staff
from app.db.session import get_db
from app.models import Business, Category, Profile
from app.models.enums import DirectoryStatus, EntryKind
from app.services.npi import (
    DEFAULT_ZIPS,
    MAX_RESULTS,
    PRESETS,
    NpiClient,
    NpiError,
    Practice,
    describe,
    practices_from_results,
)
from app.services.osm import AREAS, OsmClient, OsmError, Place, places_from_elements

log = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/import", tags=["admin"])

SOURCE = "npi"


class PresetOut(BaseModel):
    key: str
    label: str


class NpiOptions(BaseModel):
    presets: list[PresetOut]
    default_zips: list[str]


class NpiImportRequest(BaseModel):
    postal_code: str = Field(pattern=r"^\d{5}$")
    preset: str


class NpiImportResult(BaseModel):
    postal_code: str
    preset: str
    records: int  # provider records the registry returned
    practices: int  # practices located in this ZIP after filtering and grouping
    created: int
    updated: int
    already_listed: int  # someone already added this phone number
    skipped_removed: int  # a moderator removed or rejected it before
    capped: bool = False  # the registry returned its maximum: some providers may be missing


@router.get("/npi", response_model=NpiOptions)
def npi_options(_: Profile = Depends(require_staff)) -> NpiOptions:
    return NpiOptions(
        presets=[PresetOut(key=p.key, label=p.label) for p in PRESETS.values()],
        default_zips=DEFAULT_ZIPS,
    )


def _merge(existing: list[str], new: list[str]) -> list[str]:
    return list(dict.fromkeys([*existing, *new]))


def _apply(business: Business, practice: Practice, categories: dict[str, int]) -> None:
    data = business.source_data or {}
    providers = _merge(data.get("providers", []), practice.providers)
    specialties = _merge(data.get("specialties", []), practice.specialties)
    is_org = data.get("is_organization", False) or practice.is_organization
    if practice.is_organization or not data.get("is_organization", False):
        business.name = practice.name[:120]
    business.source_data = {
        "providers": providers,
        "specialties": specialties,
        "npis": _merge(data.get("npis", []), practice.npis),
        "is_organization": is_org,
    }
    business.description_en = describe(specialties, providers, business.name)
    business.phone = practice.phone
    business.address = practice.address or None
    business.city = practice.city or None
    business.zip_code = practice.zip_code
    # Dental-only practices go under Dentists; anything with a physician under Doctors.
    dental = all(s.lower().startswith("dentist") for s in specialties)
    business.category_id = categories.get("dentists" if dental else "doctors")


def _phone_listed(db: Session, phone: str | None) -> bool:
    digits = "".join(c for c in phone or "" if c.isdigit())[-10:]
    if len(digits) != 10:
        return False
    return (
        db.scalar(
            select(Business.id)
            .where(
                func.regexp_replace(Business.phone, r"\D", "", "g").in_([digits, "1" + digits]),
                Business.status != DirectoryStatus.REMOVED,
            )
            .limit(1)
        )
        is not None
    )


def doctor_categories(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Category.slug, Category.id).where(Category.slug.in_(["doctors", "dentists"]))
    ).all()
    return {slug: category_id for slug, category_id in rows}


def save_practices(
    db: Session, practices: list[Practice], profile: Profile, categories: dict[str, int]
) -> dict[str, int]:
    """Create or update entries for practices (used by the API and the bulk-file command)."""
    result = Counter(created=0, updated=0, already_listed=0, skipped_removed=0)
    for practice in practices:
        existing = db.scalar(
            select(Business).where(Business.source == SOURCE, Business.external_id == practice.key)
        )
        if existing is not None:
            if existing.status in (DirectoryStatus.REMOVED, DirectoryStatus.REJECTED):
                result["skipped_removed"] += 1
                continue
            _apply(existing, practice, categories)
            result["updated"] += 1
            continue

        # A member (or another source) may already have listed this practice.
        if _phone_listed(db, practice.phone):
            result["already_listed"] += 1
            continue

        business = Business(
            kind=EntryKind.BUSINESS,
            status=DirectoryStatus.ACTIVE,
            submitted_by_id=profile.id,
            name=practice.name[:120],
            languages=[],
            source=SOURCE,
            external_id=practice.key,
        )
        _apply(business, practice, categories)
        db.add(business)
        db.flush()  # so a later practice in this batch sees it
        result["created"] += 1

    return dict(result)


@router.post("/npi", response_model=NpiImportResult)
def import_npi(
    payload: NpiImportRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_staff),
    npi: NpiClient = Depends(get_npi_client),
) -> NpiImportResult:
    preset = PRESETS.get(payload.preset)
    if preset is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown provider type")
    categories = doctor_categories(db)
    try:
        records = npi.search(payload.postal_code, preset.taxonomy)
    except NpiError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "npi_unavailable", "message": str(exc)},
        ) from exc
    practices = practices_from_results(records, payload.postal_code, preset)

    result = NpiImportResult(
        postal_code=payload.postal_code,
        preset=preset.key,
        records=len(records),
        capped=len(records) >= MAX_RESULTS,
        practices=len(practices),
        created=0,
        updated=0,
        already_listed=0,
        skipped_removed=0,
    )
    counts = save_practices(db, practices, profile, categories)
    for name, n in counts.items():
        setattr(result, name, n)
    db.commit()
    log.info("NPI import %s", result.model_dump())
    return result


# --- OpenStreetMap restaurants ---------------------------------------------------------

OSM_SOURCE = "osm"
RESTAURANTS_SLUG = "restaurants"


class OsmOptions(BaseModel):
    areas: list[PresetOut]


class OsmImportRequest(BaseModel):
    area: str


class OsmImportResult(BaseModel):
    area: str
    places: int  # named places after filtering
    created: int
    updated: int
    already_listed: int  # same phone, or same name + address, already in the directory
    skipped_removed: int


@router.get("/osm", response_model=OsmOptions)
def osm_options(_: Profile = Depends(require_staff)) -> OsmOptions:
    return OsmOptions(areas=[PresetOut(key=a.key, label=a.label) for a in AREAS.values()])


def _apply_place(business: Business, place: Place) -> None:
    business.name = place.name
    business.description_en = place.description
    business.phone = place.phone
    business.website = place.website
    business.address = place.address
    business.city = place.city
    business.zip_code = place.zip_code
    business.hours = place.hours
    business.source_data = place.data


@router.post("/osm", response_model=OsmImportResult)
def import_osm(
    payload: OsmImportRequest,
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_staff),
    osm: OsmClient = Depends(get_osm_client),
) -> OsmImportResult:
    area = AREAS.get(payload.area)
    if area is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown area")
    category_id = db.scalar(select(Category.id).where(Category.slug == RESTAURANTS_SLUG))
    try:
        elements = osm.fetch(area)
    except OsmError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail={"code": "osm_unavailable", "message": str(exc)},
        ) from exc
    places = places_from_elements(elements)

    result = OsmImportResult(
        area=area.key,
        places=len(places),
        created=0,
        updated=0,
        already_listed=0,
        skipped_removed=0,
    )
    for place in places:
        existing = db.scalar(
            select(Business).where(Business.source == OSM_SOURCE, Business.external_id == place.key)
        )
        if existing is not None:
            if existing.status in (DirectoryStatus.REMOVED, DirectoryStatus.REJECTED):
                result.skipped_removed += 1
                continue
            _apply_place(existing, place)
            result.updated += 1
            continue

        # Already listed by a member, or mapped twice (a point and a building outline).
        same_place = place.address is not None and (
            db.scalar(
                select(Business.id)
                .where(
                    func.lower(Business.name) == place.name.lower(),
                    func.lower(Business.address) == place.address.lower(),
                    Business.status != DirectoryStatus.REMOVED,
                )
                .limit(1)
            )
            is not None
        )
        if same_place or _phone_listed(db, place.phone):
            result.already_listed += 1
            continue

        business = Business(
            kind=EntryKind.BUSINESS,
            status=DirectoryStatus.ACTIVE,
            category_id=category_id,
            submitted_by_id=profile.id,
            name=place.name,
            languages=[],
            source=OSM_SOURCE,
            external_id=place.key,
        )
        _apply_place(business, place)
        db.add(business)
        db.flush()
        result.created += 1

    db.commit()
    log.info("OSM import %s", result.model_dump())
    return result
