"""Search assistant ("dentist in Aldie"): Claude searches the directory and marketplace
through read-only tools and answers with a short reply plus entries shown as cards.

The browser keeps the conversation and sends it with each question. Nothing is saved
except the usage log.
"""

import logging
import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_search_agent, get_storage
from app.api.routes.ai import ai_error, check_ai_rate_limit
from app.api.routes.businesses import directory_query, to_out
from app.api.routes.listings import search_listings
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import AIUsage, Category, Profile
from app.models.enums import CategoryKind, Language, ListingType
from app.schemas.business import LANGUAGE_CODES, BusinessOut
from app.schemas.listing import ListingOut
from app.services.ai_intake import CategoryChoice, ChatMessage
from app.services.ai_search import (
    SearchAgent,
    SearchDirectoryArgs,
    SearchError,
    SearchMarketplaceArgs,
    SearchUsage,
)
from app.services.storage import PhotoStorage

log = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])

FEATURE = "search_assistant"
MAX_MESSAGES = 30
MAX_CONVERSATION_CHARS = 12_000
TOOL_LIMIT = 10  # results per tool call
MAX_CARDS = 6


class AskMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=1000)


class AskRequest(BaseModel):
    messages: list[AskMessage] = Field(min_length=1, max_length=MAX_MESSAGES)
    lang: Language = Language.EN

    @model_validator(mode="after")
    def _check(self) -> "AskRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user")
        if sum(len(m.content) for m in self.messages) > MAX_CONVERSATION_CHARS:
            raise ValueError("This conversation is too long. Please start a new one.")
        return self


class AskResponse(BaseModel):
    reply: str
    businesses: list[BusinessOut]
    listings: list[ListingOut]


def _clip(text: str | None, limit: int) -> str | None:
    if not text:
        return None
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


class DatabaseTools:
    """The assistant's read-only tools. Remembers every entry it returned, so the answer
    can only show entries that really came from a search in this turn."""

    def __init__(
        self,
        db: Session,
        settings: Settings,
        storage: PhotoStorage | None,
        viewer: Profile,
        directory_slugs: set[str],
        marketplace_slugs: set[str],
    ) -> None:
        self._db = db
        self._settings = settings
        self._storage = storage
        self._viewer = viewer
        self._directory_slugs = directory_slugs
        self._marketplace_slugs = marketplace_slugs
        self.businesses: dict[str, BusinessOut] = {}
        self.listings: dict[str, ListingOut] = {}

    def search_directory(self, args: SearchDirectoryArgs) -> dict[str, Any]:
        if args.category_slug and args.category_slug not in self._directory_slugs:
            raise ValueError(f"Unknown directory category {args.category_slug!r}")
        language = args.language.lower() if args.language else None
        if language and language not in LANGUAGE_CODES:
            raise ValueError(f"Unknown language code {args.language!r}")
        rows, total = directory_query(
            self._db,
            q=(args.query or "")[:100] or None,
            category=args.category_slug,
            language=language,
            towns=[t[:80] for t in args.towns[:10]],
            limit=TOOL_LIMIT,
        )
        results = []
        for b in rows:
            out = to_out(b, signed_in=True, viewer=self._viewer)
            self.businesses[str(out.id)] = out
            results.append(
                {
                    "id": str(out.id),
                    "name": out.name,
                    "category": out.category.slug if out.category else None,
                    "kind": out.kind.value,
                    "town": out.city,
                    "serves": out.service_area,
                    "hours": out.hours,
                    "languages": out.languages,
                    "phone": out.phone,
                    "verified": out.is_verified,
                    "from_public_records": out.source is not None,
                    "about": _clip(out.description_en, 240),
                }
            )
        return {"total": total, "results": results}

    def search_marketplace(self, args: SearchMarketplaceArgs) -> dict[str, Any]:
        if args.category_slug and args.category_slug not in self._marketplace_slugs:
            raise ValueError(f"Unknown marketplace category {args.category_slug!r}")
        query = (args.query or "")[:100] or None
        page = search_listings(
            db=self._db,
            settings=self._settings,
            storage=self._storage,
            q=query,
            listing_type=ListingType(args.listing_type) if args.listing_type else None,
            category=args.category_slug,
            lat=None,
            lng=None,
            radius_km=None,
            sort="relevance" if query else "newest",
            limit=TOOL_LIMIT,
            offset=0,
        )
        results = []
        for item in page.items:
            self.listings[str(item.id)] = item
            results.append(
                {
                    "id": str(item.id),
                    "title": item.title_en or item.title_te,
                    "type": item.listing_type.value,
                    "price_usd": None if item.price_cents is None else item.price_cents / 100,
                    "negotiable": item.is_negotiable,
                    "town": item.city,
                    "category": item.category.slug if item.category else None,
                    "posted": item.created_at.date().isoformat(),
                    "about": _clip(item.description_en, 200),
                }
            )
        return {"total": page.total, "results": results}


def _pick(ids: list[str], found: dict[str, Any]) -> list[Any]:
    """Entries the model chose, in its order, limited to what the tools really returned."""
    picked = []
    for raw in dict.fromkeys(ids):
        try:
            key = str(uuid.UUID(raw))
        except ValueError:
            continue
        if key in found:
            picked.append(found[key])
    return picked[:MAX_CARDS]


@router.post("/ask", response_model=AskResponse)
def ask(
    payload: AskRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    storage: PhotoStorage | None = Depends(get_storage),
    profile: Profile = Depends(get_current_profile),
    agent: SearchAgent = Depends(get_search_agent),
) -> AskResponse:
    check_ai_rate_limit(
        db,
        profile,
        settings,
        feature=FEATURE,
        limits=(settings.ai_chat_turns_per_hour, settings.ai_chat_turns_per_day),
    )
    usage = AIUsage(profile_id=profile.id, feature=FEATURE, outcome="pending")
    db.add(usage)
    db.commit()

    categories = db.scalars(
        select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order)
    ).all()
    directory = [c for c in categories if c.kind == CategoryKind.BUSINESS]
    marketplace = [c for c in categories if c.kind == CategoryKind.MARKETPLACE]
    tools = DatabaseTools(
        db,
        settings,
        storage,
        profile,
        {c.slug for c in directory},
        {c.slug for c in marketplace},
    )

    def record(outcome: str, result: SearchUsage | None) -> None:
        usage.outcome = outcome
        if result is not None:
            for name in (
                "model",
                "request_id",
                "input_tokens",
                "output_tokens",
                "cache_read_tokens",
                "cost_usd",
                "latency_ms",
            ):
                setattr(usage, name, getattr(result, name))
        db.commit()

    try:
        result = agent.answer(
            [ChatMessage(m.role, m.content) for m in payload.messages],
            tools,
            [CategoryChoice(c.slug, c.name_en) for c in directory],
            [CategoryChoice(c.slug, c.name_en) for c in marketplace],
            payload.lang.value,
            date.today().isoformat(),
        )
    except SearchError as exc:
        record(exc.outcome, exc.usage)
        raise ai_error(
            status.HTTP_502_BAD_GATEWAY,
            "ai_error",
            "The assistant couldn't answer just now. Please try again.",
        ) from exc

    record("ok", result.usage)
    return AskResponse(
        reply=result.answer.reply.strip()[:2000] or "…",
        businesses=_pick(result.answer.business_ids, tools.businesses),
        listings=_pick(result.answer.listing_ids, tools.listings),
    )
