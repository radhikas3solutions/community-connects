"""Directory of local businesses and individuals offering services (helpers, tutors, tailors).

New entries from members wait in a review queue until a moderator approves them.
Individuals' phone numbers and emails are shown only to signed-in members.
"""

import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func, literal_column, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_menu_reader, get_optional_user, require_staff
from app.api.photos import read_photos
from app.api.routes.ai import ai_error, check_ai_rate_limit
from app.core.config import Settings, get_settings
from app.core.security import AuthUser
from app.db.session import get_db
from app.models import AIUsage, Business, Category, MenuItem, Profile
from app.models.enums import CategoryKind, DirectoryStatus, EntryKind, UserRole
from app.schemas.business import (
    LANGUAGE_CODES,
    MAX_MENU_ITEMS,
    MAX_MENU_PRICE_CENTS,
    BusinessCreate,
    BusinessOut,
    BusinessReview,
    BusinessUpdate,
    MenuItemOut,
    MenuReplace,
    MenuSuggestion,
)
from app.schemas.common import Page
from app.services.ai_menu import MenuError, MenuReader
from app.services.osm import osm_url

log = logging.getLogger(__name__)
router = APIRouter(prefix="/businesses", tags=["directory"])

STAFF = (UserRole.MODERATOR, UserRole.ADMIN)
MENU_FEATURE = "read_menu"
MAX_PENDING_PER_USER = 20


def _is_staff(profile: Profile | None) -> bool:
    return profile is not None and profile.role in STAFF


def _can_edit(business: Business, profile: Profile | None) -> bool:
    return profile is not None and (business.submitted_by_id == profile.id or _is_staff(profile))


def _viewer(db: Session, user: AuthUser | None) -> Profile | None:
    return db.get(Profile, user.id) if user else None


def to_out(business: Business, *, signed_in: bool, viewer: Profile | None) -> BusinessOut:
    out = BusinessOut.model_validate(business, from_attributes=True)
    out.can_edit = _can_edit(business, viewer)
    if business.source == "osm" and business.external_id:
        out.source_url = osm_url(business.external_id)
    if not out.can_edit:
        out.review_note = None
    if business.kind == EntryKind.INDIVIDUAL and not signed_in:
        out.phone = out.whatsapp = out.email = None
        out.contact_hidden = True
    return out


def _get(db: Session, business_id: uuid.UUID) -> Business:
    business = db.get(Business, business_id)
    if business is None or business.status == DirectoryStatus.REMOVED:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return business


def _get_editable(db: Session, business_id: uuid.UUID, profile: Profile) -> Business:
    business = _get(db, business_id)
    if not _can_edit(business, profile):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You can't edit this entry")
    return business


def _validate_category(db: Session, category_id: int | None) -> None:
    if category_id is None:
        return
    category = db.get(Category, category_id)
    if category is None or category.kind != CategoryKind.BUSINESS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown directory category")


def _like(term: str) -> str:
    escaped = term.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def directory_query(
    db: Session,
    *,
    q: str | None = None,
    category: str | None = None,
    kind: EntryKind | None = None,
    language: str | None = None,
    towns: list[str] | None = None,
    limit: int = 24,
    offset: int = 0,
) -> tuple[list[Business], int]:
    """Active entries matching the filters. `towns` matches an entry's city or service area
    (any of them). Shared by the search endpoint and the search assistant."""
    stmt = select(Business).where(Business.status == DirectoryStatus.ACTIVE)
    if category:
        stmt = stmt.join(Category, Business.category_id == Category.id).where(
            Category.slug == category
        )
    if kind:
        stmt = stmt.where(Business.kind == kind)
    if language:
        if language not in LANGUAGE_CODES:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown language code")
        stmt = stmt.where(Business.languages.contains([language]))
    town_filters = []
    for town in towns or []:
        if town.strip():
            pattern = _like(town)
            town_filters += [
                Business.city.ilike(pattern, escape="\\"),
                Business.service_area.ilike(pattern, escape="\\"),
            ]
    if town_filters:
        stmt = stmt.where(or_(*town_filters))
    tsquery = None
    if q and q.strip():
        tsquery = func.websearch_to_tsquery(literal_column("'english'::regconfig"), q)
        pattern = _like(q)
        stmt = stmt.where(
            or_(
                Business.search_vector.op("@@")(tsquery),
                Business.name.ilike(pattern, escape="\\"),
                Business.name_te.ilike(pattern, escape="\\"),
                Business.description_te.ilike(pattern, escape="\\"),
            )
        )

    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    stmt = stmt.order_by(Business.is_verified.desc())
    if tsquery is not None:
        stmt = stmt.order_by(func.ts_rank(Business.search_vector, tsquery).desc())
    stmt = stmt.order_by(func.lower(Business.name))
    rows = list(db.scalars(stmt.limit(limit).offset(offset)).unique().all())
    return rows, total


@router.get("", response_model=Page[BusinessOut])
def search_directory(
    db: Session = Depends(get_db),
    user: AuthUser | None = Depends(get_optional_user),
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, description="Category slug"),
    kind: EntryKind | None = None,
    language: str | None = Query(default=None, description="Language spoken, e.g. te"),
    city: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=24, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[BusinessOut]:
    rows, total = directory_query(
        db,
        q=q,
        category=category,
        kind=kind,
        language=language,
        towns=[city] if city else None,
        limit=limit,
        offset=offset,
    )
    viewer = _viewer(db, user)
    items = [to_out(b, signed_in=user is not None, viewer=viewer) for b in rows]
    return Page(items=items, total=total, limit=limit, offset=offset)


@router.get("/mine", response_model=list[BusinessOut])
def my_entries(
    db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)
) -> list[BusinessOut]:
    rows = db.scalars(
        select(Business)
        .where(Business.submitted_by_id == profile.id, Business.status != DirectoryStatus.REMOVED)
        .order_by(Business.created_at.desc())
    ).all()
    return [to_out(b, signed_in=True, viewer=profile) for b in rows]


@router.get("/review-queue", response_model=list[BusinessOut])
def review_queue(
    db: Session = Depends(get_db), profile: Profile = Depends(require_staff)
) -> list[BusinessOut]:
    rows = db.scalars(
        select(Business)
        .where(Business.status == DirectoryStatus.PENDING_REVIEW)
        .order_by(Business.created_at)
    ).all()
    return [to_out(b, signed_in=True, viewer=profile) for b in rows]


@router.get("/{business_id}", response_model=BusinessOut)
def get_entry(
    business_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: AuthUser | None = Depends(get_optional_user),
) -> BusinessOut:
    business = _get(db, business_id)
    viewer = _viewer(db, user)
    if business.status != DirectoryStatus.ACTIVE and not _can_edit(business, viewer):
        # Pending and rejected entries are visible only to whoever added them, and staff.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return to_out(business, signed_in=user is not None, viewer=viewer)


@router.post("", response_model=BusinessOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    payload: BusinessCreate,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
) -> BusinessOut:
    _validate_category(db, payload.category_id)
    staff = _is_staff(profile)
    if not staff:
        pending = db.scalar(
            select(func.count())
            .select_from(Business)
            .where(
                Business.submitted_by_id == profile.id,
                Business.status == DirectoryStatus.PENDING_REVIEW,
            )
        )
        if (pending or 0) >= MAX_PENDING_PER_USER:
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "You have many entries waiting for review. Please wait until they're approved.",
            )
    data = payload.model_dump(exclude_none=True)
    business = Business(**data, submitted_by_id=profile.id)
    if staff:
        business.status = DirectoryStatus.ACTIVE
        business.reviewed_at = datetime.now(UTC)
    db.add(business)
    db.commit()
    db.refresh(business)
    return to_out(business, signed_in=True, viewer=profile)


@router.patch("/{business_id}", response_model=BusinessOut)
def update_entry(
    business_id: uuid.UUID,
    payload: BusinessUpdate,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
) -> BusinessOut:
    business = _get_editable(db, business_id, profile)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes and not changes["name"]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "A name is required")
    if "category_id" in changes:
        _validate_category(db, changes["category_id"])
    if business.kind == EntryKind.INDIVIDUAL:
        changes.pop("address", None)
    if "languages" in changes and changes["languages"] is None:
        changes["languages"] = []
    for key, value in changes.items():
        setattr(business, key, value)
    if not (business.phone or business.whatsapp or business.email or business.website):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Add at least one way to contact them"
        )
    if business.status == DirectoryStatus.REJECTED and not _is_staff(profile):
        business.status = DirectoryStatus.PENDING_REVIEW  # edited after rejection: resubmit
    db.commit()
    db.refresh(business)
    return to_out(business, signed_in=True, viewer=profile)


@router.post("/{business_id}/review", response_model=BusinessOut)
def review_entry(
    business_id: uuid.UUID,
    payload: BusinessReview,
    db: Session = Depends(get_db),
    profile: Profile = Depends(require_staff),
) -> BusinessOut:
    business = _get(db, business_id)
    if payload.action == "approve":
        business.status = DirectoryStatus.ACTIVE
        business.review_note = None
    else:
        business.status = DirectoryStatus.REJECTED
        business.review_note = payload.note
    if payload.is_verified is not None:
        business.is_verified = payload.is_verified
    business.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(business)
    return to_out(business, signed_in=True, viewer=profile)


@router.delete("/{business_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    business_id: uuid.UUID,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
) -> None:
    business = _get_editable(db, business_id, profile)
    business.status = DirectoryStatus.REMOVED  # soft delete: keeps moderation history
    db.commit()


# ---------------------------------------------------------------- menu


@router.put("/{business_id}/menu", response_model=BusinessOut)
def replace_menu(
    business_id: uuid.UUID,
    payload: MenuReplace,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
) -> BusinessOut:
    """Replace the whole menu (the editor sends the full, reviewed list)."""
    business = _get_editable(db, business_id, profile)
    business.menu.clear()
    db.flush()
    business.menu.extend(
        MenuItem(**item.model_dump(), position=i) for i, item in enumerate(payload.items)
    )
    db.commit()
    db.refresh(business)
    return to_out(business, signed_in=True, viewer=profile)


def _price_cents(usd: float | None) -> int | None:
    if usd is None or usd < 0:
        return None
    return min(round(usd * 100), MAX_MENU_PRICE_CENTS)


def _clip(text: str | None, limit: int) -> str | None:
    if text is None:
        return None
    text = " ".join(text.split())[:limit].rstrip()
    return text or None


@router.post("/{business_id}/menu/read-photos", response_model=MenuSuggestion)
def read_menu_photos(
    business_id: uuid.UUID,
    photos: list[UploadFile] = File(..., description="1-5 photos of the menu"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    profile: Profile = Depends(get_current_profile),
    reader: MenuReader = Depends(get_menu_reader),
) -> MenuSuggestion:
    """Read dishes from menu photos. Nothing is saved: the editor reviews the list, then
    saves it with `PUT /businesses/{id}/menu`. Photos are not stored."""
    business = _get_editable(db, business_id, profile)
    processed = read_photos(photos, settings, max_count=settings.max_photos_per_listing)
    check_ai_rate_limit(db, profile, settings, feature=MENU_FEATURE)

    usage = AIUsage(
        profile_id=profile.id, feature=MENU_FEATURE, outcome="pending", business_id=business.id
    )
    db.add(usage)
    db.commit()

    def record(outcome: str, result: object | None) -> None:
        usage.outcome = outcome
        if result is not None:
            for field in (
                "model",
                "request_id",
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cost_usd",
                "latency_ms",
            ):
                setattr(usage, field, getattr(result, field))
        db.commit()

    try:
        result = reader.read([p.data for p in processed], business.name)
    except MenuError as exc:
        record(exc.outcome, exc.result)
        if exc.outcome == "refused":
            raise ai_error(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                "unclear_photo",
                "We couldn't read a menu in these photos.",
            ) from exc
        raise ai_error(status.HTTP_502_BAD_GATEWAY, "ai_error", str(exc)) from exc

    extraction = result.extraction
    if extraction.problem != "none" or not extraction.items:
        record("rejected", result)
        message = (
            "These photos don't look like a menu."
            if extraction.problem == "not_a_menu"
            else "We couldn't read the menu. Try brighter, straighter photos, one page each."
        )
        raise ai_error(status.HTTP_422_UNPROCESSABLE_CONTENT, extraction.problem, message)

    record("ok", result)
    log.info("ai.%s business=%s items=%d", MENU_FEATURE, business.id, len(extraction.items))
    items = []
    for item in extraction.items[:MAX_MENU_ITEMS]:
        name = _clip(item.name, 160)
        if name is None:
            continue
        items.append(
            MenuItemOut(
                section=_clip(item.section, 80),
                name=name,
                name_te=_clip(item.name_te, 240),
                description=_clip(item.description, 500),
                price_cents=_price_cents(item.price_usd),
                is_vegetarian=item.is_vegetarian,
            )
        )
    return MenuSuggestion(items=items)
