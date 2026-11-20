"""Chat assistant that helps someone add a business or service to the directory.

Each turn is one Claude call returning a short reply plus the full, updated draft. The
assistant never saves anything: the person reviews the preview and submits it themselves,
and the entry then goes through the normal moderator review.
"""

import json
import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal, Protocol

import anthropic
from pydantic import BaseModel, ValidationError

from app.core.config import Settings
from app.services.ai_listing import FALLBACK_BETA, estimate_cost

log = logging.getLogger(__name__)


class IntakeDraft(BaseModel):
    """Everything known so far about the entry. null = not known yet."""

    kind: Literal["business", "individual"] | None
    category_slug: str | None
    name: str | None
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
    # True: the person is listing themselves or their own business. False: someone else.
    is_self: bool | None
    # Only when is_self is false and the person said the one being listed agreed.
    other_person_agreed: bool | None


class IntakeTurn(BaseModel):
    """Structured output schema Claude must return each turn."""

    reply: str
    draft: IntakeDraft


OUTPUT_FORMAT = {
    "type": "json_schema",
    "schema": anthropic.transform_schema(IntakeTurn.model_json_schema()),
}

EMPTY_DRAFT = IntakeDraft(
    kind=None,
    category_slug=None,
    name=None,
    name_te=None,
    description_en=None,
    description_te=None,
    phone=None,
    whatsapp=None,
    email=None,
    website=None,
    address=None,
    city=None,
    zip_code=None,
    service_area=None,
    hours=None,
    languages=[],
    is_self=None,
    other_person_agreed=None,
)

SYSTEM_PROMPT = """\
You are the friendly assistant on AskMitra, a neighborhood website in Northern \
Virginia used by many Indian and Telugu-speaking families. You help people add a \
business or a service to the local directory by chatting: a plumber, doctor, tutor, \
tailor, cook, nanny, restaurant, shop and so on. Many are not comfortable with forms, \
so keep it easy.

How the conversation goes:
- Each turn, read the conversation and the current draft, update the draft with \
anything new the person said, and reply.
- Ask for at most two things at a time, most important first: what they offer \
(category), their name or business name, a US phone number customers can call \
(required: entries without one are not listed), then the town or \
areas they serve, hours, and languages spoken. Email, website and a street address are \
optional; don't push for them.
- Work out whether this is a business (shop, clinic, restaurant, office: has a public \
address) or an individual working on their own (helper, tutor, home cook, independent \
plumber). Individuals' home addresses are never published, so never ask an individual \
for a street address, and leave address null for them even if they give one.
- Work out whether they are listing themselves (is_self true) or someone else. If \
someone else, ask whether that person agreed to be listed with these contact details, \
and set other_person_agreed only from their answer.
- Never ask for something the current draft already has, unless they seem to have \
made a mistake.
- Once you have category, name and a way to contact them, tell them to check the \
preview and press the submit button when it looks right: it is labelled "Submit for \
review" on the English site and "సమీక్షకు పంపండి" on the Telugu site. A moderator checks \
every entry before it appears. You cannot submit or publish anything yourself, so never say \
it has been added or published.

Writing the draft:
- Keep every value from the current draft unless the person changes it. Use null for \
anything not known. Never invent details they didn't give.
- category_slug must be one of the slugs listed below, or null if none fits.
- description_en: 1-3 plain sentences about what they offer, written from what they \
told you, as the business would describe itself to customers. description_te: the same \
in natural, everyday Telugu, in Telugu script (English words Telugu speakers use, like \
plumber or AC, spelled in Telugu letters). name_te: their name in Telugu script.
- phone and whatsapp exactly as given. whatsapp is shown as a "message on WhatsApp" \
button, so fill it only when they say customers may contact them on WhatsApp (if their \
phone is also on WhatsApp, repeat the phone number there). Otherwise leave it null. Once \
you have their phone, ask once whether customers can message them on WhatsApp.
- languages: two-letter codes of languages they speak: en, te, hi, ta, kn, ml, mr, gu, \
bn, ur, pa.
- hours in short form, e.g. "Mon-Fri 8am-6pm".

Your reply:
- Reply in the language the person writes in (Telugu in Telugu script if they write \
Telugu; English otherwise). The site's current language is given below as a hint.
- Short, warm and plain: one to three sentences, no markdown, no bullet lists, no \
emojis beyond one at most.
- If they ask about something unrelated, say briefly that you can only help add \
directory entries, and point them to the rest of the site.

Directory categories (slug: name):
{categories}"""


@dataclass(frozen=True)
class CategoryChoice:
    slug: str
    name_en: str


@dataclass(frozen=True)
class ChatMessage:
    role: Literal["user", "assistant"]
    content: str


@dataclass(frozen=True)
class IntakeResult:
    turn: IntakeTurn
    model: str
    request_id: str | None
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    latency_ms: int

    @property
    def cost_usd(self) -> Decimal | None:
        return estimate_cost(
            self.model, self.input_tokens, self.output_tokens, self.cache_read_tokens
        )


class IntakeError(RuntimeError):
    def __init__(self, message: str, *, outcome: str = "error", result: IntakeResult | None = None):
        super().__init__(message)
        self.outcome = outcome
        self.result = result


class IntakeAssistant(Protocol):
    def turn(
        self,
        messages: list[ChatMessage],
        draft: IntakeDraft,
        categories: list[CategoryChoice],
        site_language: str,
    ) -> IntakeResult: ...


def build_request(
    messages: list[ChatMessage],
    draft: IntakeDraft,
    categories: list[CategoryChoice],
    site_language: str,
) -> tuple[str, list[dict]]:
    system = SYSTEM_PROMPT.replace(
        "{categories}", "\n".join(f"- {c.slug}: {c.name_en}" for c in categories)
    )
    convo: list[dict] = [{"role": m.role, "content": m.content} for m in messages]
    # Operator context for this turn goes in a trailing system message, after the
    # person's latest message, so it can't be confused with what they wrote.
    convo.append(
        {
            "role": "system",
            "content": (
                f"Site language: {'Telugu' if site_language == 'te' else 'English'}.\n"
                f"Current draft (JSON):\n{json.dumps(draft.model_dump(), ensure_ascii=False)}"
            ),
        }
    )
    return system, convo


class ClaudeIntakeAssistant:
    def __init__(self, settings: Settings, client: anthropic.Anthropic | None = None) -> None:
        self._model = settings.claude_model
        self._client = client or anthropic.Anthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.claude_timeout_seconds,
            max_retries=1,
        )

    def turn(
        self,
        messages: list[ChatMessage],
        draft: IntakeDraft,
        categories: list[CategoryChoice],
        site_language: str,
    ) -> IntakeResult:
        system, convo = build_request(messages, draft, categories, site_language)
        started = time.monotonic()
        try:
            response = self._client.beta.messages.create(
                model=self._model,
                max_tokens=16000,
                system=system,
                messages=convo,  # type: ignore[arg-type]
                # A quick, conversational task: low effort keeps replies fast.
                output_config={"effort": "low", "format": OUTPUT_FORMAT},
                # Later turns of the same chat reuse the cached system prompt and history.
                cache_control={"type": "ephemeral"},
                betas=[FALLBACK_BETA],
                fallbacks="default",
            )
        except anthropic.RateLimitError as exc:
            raise IntakeError("AI service is busy. Please try again in a minute.") from exc
        except anthropic.APIStatusError as exc:
            log.error("Claude API error %s request_id=%s", exc.status_code, exc.request_id)
            raise IntakeError("AI service error") from exc
        except anthropic.APIConnectionError as exc:
            log.error("Claude API unreachable: %s", exc)
            raise IntakeError("AI service unreachable") from exc

        usage = response.usage

        def result(turn: IntakeTurn) -> IntakeResult:
            return IntakeResult(
                turn=turn,
                model=str(response.model),
                request_id=getattr(response, "_request_id", None),
                # With caching on, most of the prompt is billed as a cache write; count it
                # as input so the cost log isn't understated (writes cost 1.25x, logged at 1x).
                input_tokens=usage.input_tokens + (usage.cache_creation_input_tokens or 0),
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens or 0,
                latency_ms=int((time.monotonic() - started) * 1000),
            )

        fallback_turn = IntakeTurn(reply="", draft=draft)
        if response.stop_reason == "refusal":
            raise IntakeError("AI declined", outcome="refused", result=result(fallback_turn))
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            turn = IntakeTurn.model_validate_json(text)
        except ValidationError as exc:
            log.error("Unreadable intake turn (stop_reason=%s): %s", response.stop_reason, exc)
            raise IntakeError(
                "AI returned an unreadable reply", result=result(fallback_turn)
            ) from exc
        return result(turn)
