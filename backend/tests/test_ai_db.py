"""AI draft -> edit -> publish flow against PostGIS, with fake storage and a fake Claude."""

import io
import uuid
from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.api.deps import get_drafter, get_storage
from app.core.config import get_settings
from app.db.session import get_sessionmaker
from app.models import AIUsage
from app.services.ai_listing import DraftError, DraftRequest, DraftResult, ListingDraft
from app.services.storage import InMemoryStorage
from tests.conftest import auth_header, make_token
from tests.images import make_photo

pytestmark = pytest.mark.db

DRAFT = ListingDraft(
    problem="none",
    title_en="Kanchipuram silk saree, maroon and gold",
    description_en="Pure silk saree with zari border, worn twice. Blouse piece included.",
    title_te="కంచిపట్టు చీర, మెరూన్ మరియు బంగారు రంగు",
    description_te="జరీ అంచుతో పట్టు చీర, రెండుసార్లు కట్టుకున్నాను.",
    category_slug="ethnic-wear",
    condition="like_new",
    price_low_usd=120,
    price_high_usd=200,
    suggested_price_usd=150,
    confidence=0.9,
)


class FakeDrafter:
    def __init__(self, draft: ListingDraft = DRAFT, error: DraftError | None = None) -> None:
        self.draft_value, self.error, self.requests = draft, error, []

    def draft(self, request: DraftRequest) -> DraftResult:
        self.requests.append(request)
        if self.error:
            raise self.error
        return DraftResult(
            draft=self.draft_value,
            model="claude-opus-5-5",
            request_id="req_fake",
            input_tokens=4000,
            output_tokens=600,
            cache_read_tokens=0,
            latency_ms=1234,
        )


@pytest.fixture
def storage() -> InMemoryStorage:
    return InMemoryStorage()


@pytest.fixture
def drafter() -> FakeDrafter:
    return FakeDrafter()


@pytest.fixture
def ai_client(
    db_client: TestClient, storage: InMemoryStorage, drafter: FakeDrafter
) -> Iterator[TestClient]:
    overrides = db_client.app.dependency_overrides  # type: ignore[attr-defined]
    overrides[get_storage] = lambda: storage
    overrides[get_drafter] = lambda: drafter
    yield db_client
    overrides.clear()


def _user() -> tuple[uuid.UUID, dict[str, str]]:
    uid = uuid.uuid4()
    return uid, auth_header(make_token(uid))


def _photos(n: int = 2, **kw) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("photos", (f"p{i}.jpg", make_photo(**kw), "image/jpeg")) for i in range(n)]


def _draft(client: TestClient, headers: dict, n: int = 2, **data) -> dict:
    data.setdefault("listing_type", "sell")
    r = client.post("/api/v1/ai/draft-listing", files=_photos(n), data=data, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_draft_creates_private_bilingual_listing_with_photos(
    ai_client: TestClient, storage: InMemoryStorage, drafter: FakeDrafter
) -> None:
    uid, h = _user()
    listing = _draft(ai_client, h, note="Worn at a wedding")

    assert listing["status"] == "draft"
    assert listing["title_en"] == DRAFT.title_en
    assert listing["title_te"] == DRAFT.title_te
    assert listing["category"]["slug"] == "ethnic-wear"
    assert listing["condition"] == "like_new"
    assert listing["price_cents"] == 15000
    assert (listing["ai_price_low_cents"], listing["ai_price_high_cents"]) == (12000, 20000)
    assert len(listing["images"]) == 2
    assert all(i["url"].startswith("https://storage.test/") for i in listing["images"])

    # Claude saw the photos, the seller's note and the marketplace categories
    req = drafter.requests[0]
    assert len(req.images) == 2 and req.seller_note == "Worn at a wedding"
    assert "ethnic-wear" in {c.slug for c in req.categories}
    assert "temples" not in {c.slug for c in req.categories}  # business category

    # Stored under the owner's folder, metadata stripped
    paths = list(storage.objects)
    assert all(p.startswith(f"{uid}/{listing['id']}/") for p in paths)
    stored = Image.open(io.BytesIO(storage.objects[paths[0]][0]))
    assert len(stored.getexif()) == 0

    # Drafts are private
    assert ai_client.get("/api/v1/listings").json()["total"] == 0
    assert ai_client.get(f"/api/v1/listings/{listing['id']}").status_code == 404
    _, stranger = _user()
    assert ai_client.get(f"/api/v1/listings/{listing['id']}", headers=stranger).status_code == 404
    assert ai_client.get(f"/api/v1/listings/{listing['id']}", headers=h).status_code == 200


def test_usage_and_cost_logged(ai_client: TestClient) -> None:
    uid, h = _user()
    listing = _draft(ai_client, h)
    with get_sessionmaker()() as s:
        row = s.scalars(select(AIUsage).where(AIUsage.profile_id == uid)).one()
    assert row.outcome == "ok"
    assert str(row.listing_id) == listing["id"]
    assert (row.input_tokens, row.output_tokens) == (4000, 600)
    assert row.cost_usd == Decimal("0.028000")
    assert row.request_id == "req_fake"


def test_edit_then_publish(ai_client: TestClient) -> None:
    _, h = _user()
    listing = _draft(ai_client, h)
    url = f"/api/v1/listings/{listing['id']}"

    r = ai_client.patch(url, json={"price_cents": 14000, "title_en": "Silk saree"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "draft"

    r = ai_client.patch(url, json={"status": "active"}, headers=h)
    assert r.status_code == 200 and r.json()["status"] == "active"

    found = ai_client.get("/api/v1/listings", params={"q": "saree"}).json()
    assert found["total"] == 1
    assert len(found["items"][0]["images"]) == 2
    assert ai_client.get(url).status_code == 200


def test_cannot_publish_sale_without_price(ai_client: TestClient) -> None:
    _, h = _user()
    listing = _draft(ai_client, h)
    url = f"/api/v1/listings/{listing['id']}"
    r = ai_client.patch(url, json={"price_cents": None, "status": "active"}, headers=h)
    assert r.status_code == 422


def test_free_listing_draft(ai_client: TestClient) -> None:
    _, h = _user()
    listing = _draft(ai_client, h, listing_type="free")
    assert listing["listing_type"] == "free"
    assert listing["price_cents"] == 0
    assert listing["ai_price_low_cents"] is None


def test_wanted_posts_not_supported(ai_client: TestClient) -> None:
    _, h = _user()
    r = ai_client.post(
        "/api/v1/ai/draft-listing", files=_photos(1), data={"listing_type": "buy"}, headers=h
    )
    assert r.status_code == 422


@pytest.mark.parametrize("problem", ["no_item", "prohibited", "unclear_photo"])
def test_flagged_photos_create_nothing(
    ai_client: TestClient, storage: InMemoryStorage, drafter: FakeDrafter, problem: str
) -> None:
    uid, h = _user()
    drafter.draft_value = DRAFT.model_copy(update={"problem": problem})
    r = ai_client.post("/api/v1/ai/draft-listing", files=_photos(1), headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == problem
    assert storage.objects == {}
    assert ai_client.get("/api/v1/listings/mine", headers=h).json() == []
    with get_sessionmaker()() as s:
        assert s.scalars(select(AIUsage.outcome).where(AIUsage.profile_id == uid)).all() == [
            "rejected"
        ]


def test_ai_failure_returns_502(ai_client: TestClient, drafter: FakeDrafter) -> None:
    _, h = _user()
    drafter.error = DraftError("AI service unreachable")
    r = ai_client.post("/api/v1/ai/draft-listing", files=_photos(1), headers=h)
    assert r.status_code == 502
    assert r.json()["detail"]["code"] == "ai_error"


def test_refusal_maps_to_prohibited(ai_client: TestClient, drafter: FakeDrafter) -> None:
    _, h = _user()
    drafter.error = DraftError("declined", outcome="refused")
    r = ai_client.post("/api/v1/ai/draft-listing", files=_photos(1), headers=h)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "prohibited"


def test_rate_limited_per_user(ai_client: TestClient) -> None:
    settings = get_settings().model_copy(update={"ai_drafts_per_hour": 2})
    ai_client.app.dependency_overrides[get_settings] = lambda: settings  # type: ignore[attr-defined]
    _, h = _user()
    _draft(ai_client, h, n=1)
    _draft(ai_client, h, n=1)
    r = ai_client.post("/api/v1/ai/draft-listing", files=_photos(1), headers=h)
    assert r.status_code == 429
    assert r.headers["retry-after"] == "3600"
    # Another user is unaffected
    _, other = _user()
    _draft(ai_client, other, n=1)


def test_photo_validation(ai_client: TestClient) -> None:
    _, h = _user()
    url = "/api/v1/ai/draft-listing"
    r = ai_client.post(url, files=_photos(6), headers=h)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "too_many_photos"
    bad = [("photos", ("x.jpg", b"definitely not a jpeg", "image/jpeg"))]
    r = ai_client.post(url, files=bad, headers=h)
    assert r.status_code == 415 and r.json()["detail"]["code"] == "bad_photo"


def test_requires_auth(ai_client: TestClient) -> None:
    r = ai_client.post("/api/v1/ai/draft-listing", files=_photos(1))
    assert r.status_code == 401


def test_unconfigured_services_return_503(db_client: TestClient) -> None:
    # No overrides: test settings have neither Supabase storage nor an Anthropic key.
    _, h = _user()
    r = db_client.post("/api/v1/ai/draft-listing", files=_photos(1), headers=h)
    assert r.status_code == 503


def test_add_and_delete_photos(ai_client: TestClient, storage: InMemoryStorage) -> None:
    _, h = _user()
    listing = _draft(ai_client, h, n=4)
    base = f"/api/v1/listings/{listing['id']}/images"

    r = ai_client.post(base, files=_photos(1), headers=h)
    assert r.status_code == 201 and len(r.json()["images"]) == 5
    r = ai_client.post(base, files=_photos(1), headers=h)  # sixth photo
    assert r.status_code == 422

    _, stranger = _user()
    first = listing["images"][0]["id"]
    assert ai_client.delete(f"{base}/{first}", headers=stranger).status_code == 403
    assert ai_client.delete(f"{base}/{first}", headers=h).status_code == 204
    assert len(storage.objects) == 4
    after = ai_client.get(f"/api/v1/listings/{listing['id']}", headers=h).json()
    assert first not in {i["id"] for i in after["images"]}
