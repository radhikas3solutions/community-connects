"""AI-assisted listing creation: photos in, editable bilingual draft out."""

import logging
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_drafter, require_storage
from app.api.photos import read_photos, store_photos
from app.api.routes.listings import fetch_listing_out
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import AIUsage, Category, Listing, Profile
from app.models.enums import CategoryKind, ItemCondition, Language, ListingStatus, ListingType
from app.schemas.listing import MAX_PRICE_CENTS, ListingOut
from app.services.ai_listing import (
    CategoryChoice,
    DraftError,
    DraftRequest,
    DraftResult,
    ListingDraft,
    ListingDrafter,
)
from app.services.storage import PhotoStorage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/ai", tags=["ai"])

FEATURE = "draft_listing"
PROBLEM_MESSAGES = {
    "no_item": "We couldn't find an item to list in these photos.",
    "prohibited": "This item can't be listed on Community Connect.",
    "unclear_photo": "The photos are too unclear to identify the item. Try brighter, closer shots.",
}


def _error(
    code: int, key: str, message: str, headers: dict[str, str] | None = None
) -> HTTPException:
    return HTTPException(code, detail={"code": key, "message": message}, headers=headers)


def _check_rate_limit(db: Session, profile: Profile, settings: Settings) -> None:
    now = datetime.now(UTC)
    windows = (
        (timedelta(hours=1), settings.ai_drafts_per_hour),
        (timedelta(days=1), settings.ai_drafts_per_day),
    )
    for window, limit in windows:
        used = db.scalar(
            select(func.count())
            .select_from(AIUsage)
            .where(
                AIUsage.profile_id == profile.id,
                AIUsage.feature == FEATURE,
                AIUsage.created_at > now - window,
            )
        )
        if (used or 0) >= limit:
            raise _error(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "rate_limited",
                "You've reached the limit for AI drafts. Please try again later.",
                headers={"Retry-After": str(int(window.total_seconds()))},
            )


def _record(
    usage: AIUsage,
    outcome: str,
    result: DraftResult | None,
    listing_id: uuid.UUID | None = None,
) -> None:
    usage.outcome = outcome
    usage.listing_id = listing_id
    if result is not None:
        usage.model = result.model
        usage.request_id = result.request_id
        usage.input_tokens = result.input_tokens
        usage.output_tokens = result.output_tokens
        usage.cache_read_tokens = result.cache_read_tokens
        usage.cost_usd = result.cost_usd
        usage.latency_ms = result.latency_ms
        log.info(
            "ai.%s outcome=%s model=%s in=%d out=%d cost_usd=%s latency_ms=%d",
            FEATURE,
            outcome,
            result.model,
            result.input_tokens,
            result.output_tokens,
            result.cost_usd,
            result.latency_ms,
        )


def _cents(usd: int | None) -> int | None:
    if usd is None:
        return None
    return min(max(int(usd), 0) * 100, MAX_PRICE_CENTS)


def _clip(text: str, limit: int, *, single_line: bool = False) -> str | None:
    text = " ".join(text.split()) if single_line else text.strip()
    return text[:limit].rstrip() or None


def build_listing(
    draft: ListingDraft, listing_type: ListingType, profile: Profile, category_ids: dict[str, int]
) -> Listing:
    """Map Claude's draft onto a Listing in DRAFT status, sanitising every field."""
    low, high, suggested = (
        _cents(draft.price_low_usd),
        _cents(draft.price_high_usd),
        _cents(draft.suggested_price_usd),
    )
    if low is not None and high is not None and low > high:
        low, high = high, low
    if suggested is None and low is not None and high is not None:
        suggested = (low + high) // 2
    if listing_type == ListingType.FREE:
        low = high = None
        price = 0
    else:
        price = suggested

    title_en = _clip(draft.title_en, 140, single_line=True)
    title_te = _clip(draft.title_te, 280, single_line=True)
    if title_en is None and title_te is None:
        title_en = "Untitled item"

    try:
        condition = ItemCondition(draft.condition) if draft.condition else None
    except ValueError:
        condition = None

    return Listing(
        owner_id=profile.id,
        listing_type=listing_type,
        status=ListingStatus.DRAFT,
        source_language=Language.EN,
        title_en=title_en,
        title_te=title_te,
        description_en=_clip(draft.description_en, 5000),
        description_te=_clip(draft.description_te, 10000),
        category_id=category_ids.get(draft.category_slug or ""),
        condition=condition,
        price_cents=price,
        ai_price_low_cents=low,
        ai_price_high_cents=high,
        ai_confidence=Decimal(str(round(min(max(draft.confidence, 0.0), 1.0), 3))),
        city=profile.city,
        zip_code=profile.zip_code,
    )


@router.post(
    "/draft-listing",
    response_model=ListingOut,
    status_code=status.HTTP_201_CREATED,
    summary="Draft a bilingual listing from photos",
)
def draft_listing(
    photos: list[UploadFile] = File(..., description="1-5 photos of the item"),
    listing_type: ListingType = Form(ListingType.SELL),
    note: str | None = Form(None, max_length=500, description="Optional details from the seller"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    profile: Profile = Depends(get_current_profile),
    storage: PhotoStorage = Depends(require_storage),
    drafter: ListingDrafter = Depends(get_drafter),
) -> ListingOut:
    """Creates a listing in `draft` status. The seller edits it, then publishes it with
    `PATCH /listings/{id}` and `{"status": "active"}`."""
    if listing_type == ListingType.BUY:
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "unsupported_type",
            "AI drafts are for items you're selling or giving away",
        )
    processed = read_photos(photos, settings, max_count=settings.max_photos_per_listing)
    _check_rate_limit(db, profile, settings)

    # Reserve the slot before calling Claude so parallel requests can't exceed the limit.
    usage = AIUsage(profile_id=profile.id, feature=FEATURE, outcome="pending")
    db.add(usage)
    db.commit()

    categories = db.scalars(
        select(Category)
        .where(Category.kind == CategoryKind.MARKETPLACE, Category.is_active.is_(True))
        .order_by(Category.sort_order)
    ).all()
    request = DraftRequest(
        images=[p.data for p in processed],
        listing_type=listing_type,
        categories=[CategoryChoice(c.slug, c.name_en) for c in categories],
        seller_note=note,
    )

    try:
        result = drafter.draft(request)
    except DraftError as exc:
        _record(usage, exc.outcome, exc.result)
        db.commit()
        if exc.outcome == "refused":
            raise _error(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "prohibited", PROBLEM_MESSAGES["prohibited"]
            ) from exc
        raise _error(status.HTTP_502_BAD_GATEWAY, "ai_error", str(exc)) from exc

    draft = result.draft
    if draft.problem != "none":
        _record(usage, "rejected", result)
        db.commit()
        raise _error(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            draft.problem,
            PROBLEM_MESSAGES.get(draft.problem, PROBLEM_MESSAGES["unclear_photo"]),
        )

    listing = build_listing(draft, listing_type, profile, {c.slug: c.id for c in categories})
    db.add(listing)
    db.flush()
    try:
        rows = store_photos(storage, listing, processed)
    except HTTPException:
        db.rollback()
        _record(usage, "error", result)
        db.commit()
        raise
    db.add_all(rows)
    _record(usage, "ok", result, listing_id=listing.id)
    try:
        db.commit()
    except Exception:
        db.rollback()
        storage.delete([r.storage_path for r in rows])
        raise
    return fetch_listing_out(db, listing.id, storage)
