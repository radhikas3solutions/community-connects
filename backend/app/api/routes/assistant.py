"""Chat assistant for adding a directory entry ("I'm a plumber in Ashburn, call me at...").

The browser keeps the conversation and the draft and sends both with each message.
The assistant only suggests a draft; the person submits it with `POST /businesses`, and
it then waits for moderator review like any other entry.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field, ValidationError, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_profile, get_intake_assistant
from app.api.routes.ai import ai_error, check_ai_rate_limit
from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models import AIUsage, Category, Profile
from app.models.enums import CategoryKind, EntryKind, Language
from app.schemas.business import LANGUAGE_CODES, BusinessUpdate
from app.services.ai_intake import (
    EMPTY_DRAFT,
    CategoryChoice,
    ChatMessage,
    IntakeAssistant,
    IntakeDraft,
    IntakeError,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/assistant", tags=["assistant"])

FEATURE = "directory_assistant"
MAX_MESSAGES = 40
MAX_CONVERSATION_CHARS = 24_000

# Draft text fields and their maximum lengths (mirrors app.schemas.business).
TEXT_LIMITS: dict[str, int] = {
    "name": 120,
    "name_te": 240,
    "description_en": 3000,
    "description_te": 6000,
    "phone": 32,
    "whatsapp": 32,
    "email": 320,
    "website": 500,
    "address": 200,
    "city": 80,
    "zip_code": 10,
    "service_area": 200,
    "hours": 200,
}


class ChatMessageIn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class DirectoryDraft(BaseModel):
    """The draft as the browser holds it (also what it sends back next turn)."""

    kind: EntryKind | None = None
    category_id: int | None = None
    name: str | None = None
    name_te: str | None = None
    description_en: str | None = None
    description_te: str | None = None
    phone: str | None = None
    whatsapp: str | None = None
    email: str | None = None
    website: str | None = None
    address: str | None = None
    city: str | None = None
    zip_code: str | None = None
    service_area: str | None = None
    hours: str | None = None
    languages: list[str] = Field(default_factory=list, max_length=11)
    is_self: bool | None = None
    other_person_agreed: bool | None = None


class IntakeRequest(BaseModel):
    messages: list[ChatMessageIn] = Field(min_length=1, max_length=MAX_MESSAGES)
    draft: DirectoryDraft | None = None
    lang: Language = Language.EN

    @model_validator(mode="after")
    def _check(self) -> "IntakeRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must be from the user")
        if sum(len(m.content) for m in self.messages) > MAX_CONVERSATION_CHARS:
            raise ValueError("This conversation is too long. Please start a new one.")
        return self


class IntakeResponse(BaseModel):
    reply: str
    draft: DirectoryDraft
    # What's still needed before it can be submitted: kind, category, name, contact, consent.
    missing: list[str]
    ready: bool


def sanitize(draft: IntakeDraft, categories: dict[str, int]) -> DirectoryDraft:
    """Check every value the model produced; anything invalid is dropped, not trusted."""
    out = DirectoryDraft(
        kind=EntryKind(draft.kind) if draft.kind else None,
        category_id=categories.get(draft.category_slug or ""),
        languages=[c for c in dict.fromkeys(draft.languages) if c in LANGUAGE_CODES],
        is_self=draft.is_self,
        other_person_agreed=draft.other_person_agreed if draft.is_self is False else None,
    )
    for field, limit in TEXT_LIMITS.items():
        value = getattr(draft, field)
        if not isinstance(value, str) or not value.strip():
            continue
        value = (
            " ".join(value.split())
            if field not in ("description_en", "description_te")
            else value.strip()
        )
        try:
            checked = BusinessUpdate.model_validate({field: value[:limit]})
        except ValidationError:
            log.info("assistant: dropped invalid %s from draft", field)
            continue
        setattr(out, field, getattr(checked, field))
    if out.kind == EntryKind.INDIVIDUAL:
        out.address = None  # never collect a helper's home address
    return out


def missing_fields(d: DirectoryDraft) -> list[str]:
    missing = []
    if d.kind is None:
        missing.append("kind")
    if d.category_id is None:
        missing.append("category")
    if not d.name or len(d.name) < 2:
        missing.append("name")
    if not (d.phone or d.whatsapp or d.email or d.website):
        missing.append("contact")
    if d.kind == EntryKind.INDIVIDUAL and d.is_self is False and not d.other_person_agreed:
        missing.append("consent")
    return missing


def _to_model_draft(d: DirectoryDraft | None, slugs: dict[int, str]) -> IntakeDraft:
    if d is None:
        return EMPTY_DRAFT
    data = d.model_dump(exclude={"category_id"})
    data["kind"] = d.kind.value if d.kind else None
    data["category_slug"] = slugs.get(d.category_id) if d.category_id else None
    return IntakeDraft(**data)


@router.post("/directory-intake", response_model=IntakeResponse)
def directory_intake(
    payload: IntakeRequest,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    profile: Profile = Depends(get_current_profile),
    assistant: IntakeAssistant = Depends(get_intake_assistant),
) -> IntakeResponse:
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
        select(Category)
        .where(Category.kind == CategoryKind.BUSINESS, Category.is_active.is_(True))
        .order_by(Category.sort_order)
    ).all()
    by_slug = {c.slug: c.id for c in categories}
    by_id = {c.id: c.slug for c in categories}
    current = _to_model_draft(payload.draft, by_id)

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
        result = assistant.turn(
            [ChatMessage(m.role, m.content) for m in payload.messages],
            current,
            [CategoryChoice(c.slug, c.name_en) for c in categories],
            payload.lang.value,
        )
    except IntakeError as exc:
        record(exc.outcome, exc.result)
        raise ai_error(
            status.HTTP_502_BAD_GATEWAY,
            "ai_error",
            "The assistant couldn't answer just now. Please try again.",
        ) from exc

    record("ok", result)
    draft = sanitize(result.turn.draft, by_slug)
    missing = missing_fields(draft)
    reply = result.turn.reply.strip()[:2000] or "…"
    return IntakeResponse(reply=reply, draft=draft, missing=missing, ready=not missing)
