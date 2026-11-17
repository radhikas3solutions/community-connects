"""Unit tests for the Claude drafting service. No network: the SDK client is faked."""

import json
import uuid
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from app.api.routes.ai import build_listing
from app.core.config import Settings
from app.models import Profile
from app.models.enums import ItemCondition, ListingStatus, ListingType
from app.services.ai_listing import (
    FALLBACK_BETA,
    OUTPUT_FORMAT,
    CategoryChoice,
    ClaudeListingDrafter,
    DraftError,
    DraftRequest,
    ListingDraft,
    build_user_content,
    estimate_cost,
)
from app.services.images import process_image
from tests.images import make_photo

DRAFT = {
    "problem": "none",
    "title_en": "Brass pooja diya set",
    "description_en": "Set of 5 brass diyas, lightly used. Polished, no dents.",
    "title_te": "ఇత్తడి పూజ దీపాల సెట్",
    "description_te": "5 ఇత్తడి దీపాల సెట్, కొద్దిగా వాడినవి.",
    "category_slug": "pooja-items",
    "condition": "like_new",
    "price_low_usd": 20,
    "price_high_usd": 35,
    "suggested_price_usd": 28,
    "confidence": 0.82,
}


def _response(text: str, stop_reason: str = "end_turn", **extra: Any) -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=extra.get("stop_details"),
        content=[SimpleNamespace(type="text", text=text)] if text else [],
        usage=SimpleNamespace(input_tokens=3000, output_tokens=500, cache_read_input_tokens=None),
        model="claude-opus-5-5",
        _request_id="req_test",
    )


class FakeMessages:
    def __init__(self, response: Any = None, error: Exception | None = None) -> None:
        self.response, self.error, self.calls = response, error, []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


def _drafter(messages: FakeMessages) -> ClaudeListingDrafter:
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return ClaudeListingDrafter(Settings(anthropic_api_key="test"), client=client)  # type: ignore[arg-type]


def _request(**kw: Any) -> DraftRequest:
    photo = process_image(make_photo((3000, 2000))).data
    return DraftRequest(
        images=[photo, photo],
        listing_type=kw.get("listing_type", ListingType.SELL),
        categories=[CategoryChoice("pooja-items", "Pooja & Religious Items")],
        seller_note=kw.get("note"),
    )


def test_request_shape() -> None:
    messages = FakeMessages(_response(json.dumps(DRAFT)))
    _drafter(messages).draft(_request(note="Bought in Hyderabad"))
    call = messages.calls[0]

    assert call["model"] == "claude-opus-5-5"
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["output_config"]["effort"] == "medium"
    assert call["output_config"]["format"] == OUTPUT_FORMAT
    # Sampling parameters are rejected on the current API version; thinking is left adaptive.
    for banned in ("temperature", "top_p", "top_k", "thinking"):
        assert banned not in call

    content = call["messages"][0]["content"]
    assert [b["type"] for b in content] == ["image", "image", "text"]
    assert content[0]["source"]["media_type"] == "image/jpeg"
    assert "<seller_note>\nBought in Hyderabad\n</seller_note>" in content[-1]["text"]
    assert "pooja-items" in content[-1]["text"]


def test_images_sent_to_claude_are_capped() -> None:
    import base64
    import io

    from PIL import Image

    block = build_user_content(_request())[0]
    img = Image.open(io.BytesIO(base64.b64decode(block["source"]["data"])))
    assert max(img.size) <= 1568


def test_schema_is_strict() -> None:
    schema = OUTPUT_FORMAT["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(ListingDraft.model_fields)


def test_successful_draft_with_usage_and_cost() -> None:
    result = _drafter(FakeMessages(_response(json.dumps(DRAFT)))).draft(_request())
    assert result.draft.title_te == DRAFT["title_te"]
    assert result.request_id == "req_test"
    # 3000 * $4/M + 500 * $20/M
    assert result.cost_usd == Decimal("0.022000")


def test_refusal_is_reported_with_usage() -> None:
    resp = _response("", stop_reason="refusal", stop_details=SimpleNamespace(category="cyber"))
    with pytest.raises(DraftError) as err:
        _drafter(FakeMessages(resp)).draft(_request())
    assert err.value.outcome == "refused"
    assert err.value.result is not None and err.value.result.input_tokens == 3000


def test_truncated_json_is_an_error() -> None:
    with pytest.raises(DraftError, match="unreadable"):
        _drafter(FakeMessages(_response('{"problem": "none", "title_', "max_tokens"))).draft(
            _request()
        )


def test_api_errors_are_wrapped() -> None:
    req = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.APIConnectionError(request=req)
    with pytest.raises(DraftError, match="unreachable"):
        _drafter(FakeMessages(error=error)).draft(_request())


def test_cost_unknown_model() -> None:
    assert estimate_cost("some-future-model", 1, 1, 0) is None


def _profile() -> Profile:
    return Profile(id=uuid.uuid4(), city="Herndon", zip_code="20170")


def test_build_listing_sell() -> None:
    draft = ListingDraft(**DRAFT)
    listing = build_listing(draft, ListingType.SELL, _profile(), {"pooja-items": 7})
    assert listing.status == ListingStatus.DRAFT
    assert listing.category_id == 7
    assert listing.condition == ItemCondition.LIKE_NEW
    assert (listing.ai_price_low_cents, listing.price_cents, listing.ai_price_high_cents) == (
        2000,
        2800,
        3500,
    )
    assert listing.city == "Herndon" and listing.zip_code == "20170"


def test_build_listing_sanitises_model_output() -> None:
    draft = ListingDraft(
        **{
            **DRAFT,
            "title_en": "  A\n" + "x" * 300,
            "category_slug": "not-a-category",
            "price_low_usd": 50,
            "price_high_usd": 10,
            "suggested_price_usd": None,
            "confidence": 7.0,
        }
    )
    listing = build_listing(draft, ListingType.SELL, _profile(), {"pooja-items": 7})
    assert listing.title_en is not None and len(listing.title_en) <= 140
    assert "\n" not in listing.title_en
    assert listing.category_id is None
    assert (listing.ai_price_low_cents, listing.ai_price_high_cents) == (1000, 5000)
    assert listing.price_cents == 3000
    assert listing.ai_confidence == Decimal("1.0")


def test_build_listing_free_has_no_price() -> None:
    listing = build_listing(ListingDraft(**DRAFT), ListingType.FREE, _profile(), {})
    assert listing.price_cents == 0
    assert listing.ai_price_low_cents is None and listing.ai_price_high_cents is None
