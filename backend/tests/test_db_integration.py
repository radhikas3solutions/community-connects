"""End-to-end API tests against a real PostGIS database (skipped without TEST_DATABASE_URL)."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db.session import get_sessionmaker
from app.models import Profile
from app.models.enums import UserRole
from tests.conftest import auth_header, make_token

pytestmark = pytest.mark.db

FAIRFAX = {"lat": 38.8462, "lng": -77.3064}
ASHBURN = {"lat": 39.0438, "lng": -77.4874}  # ~28 km from Fairfax
RICHMOND = {"lat": 37.5407, "lng": -77.4360}  # ~150 km away


def _user(email: str = "seller@example.com", **meta) -> tuple[uuid.UUID, dict[str, str]]:
    uid = uuid.uuid4()
    return uid, auth_header(make_token(uid, email=email, user_metadata=meta))


def _create(client: TestClient, headers: dict, **body) -> dict:
    body.setdefault("listing_type", "sell")
    body.setdefault("title_en", "Teak dining table")
    body.setdefault("price_cents", 25000)
    r = client.post("/api/v1/listings", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def test_ready_reports_postgis(db_client: TestClient) -> None:
    r = db_client.get("/health/ready")
    assert r.status_code == 200
    assert r.json()["postgis"]


def test_profile_jit_provisioned_and_updatable(db_client: TestClient) -> None:
    uid, h = _user(full_name="Lakshmi P")
    me = db_client.get("/api/v1/me", headers=h).json()
    assert me["id"] == str(uid)
    assert me["display_name"] == "Lakshmi P"
    assert me["role"] == "user"
    assert me["preferred_language"] == "en"

    r = db_client.patch(
        "/api/v1/me", json={"preferred_language": "te", "city": "Chantilly"}, headers=h
    )
    assert r.status_code == 200
    assert r.json()["preferred_language"] == "te"
    # second call doesn't duplicate
    assert db_client.get("/api/v1/me", headers=h).json()["city"] == "Chantilly"


def test_categories_seeded_bilingual(db_client: TestClient) -> None:
    cats = db_client.get("/api/v1/categories", params={"kind": "business"}).json()
    slugs = {c["slug"] for c in cats}
    assert {"indian-grocery", "temples", "priests-pooja"} <= slugs
    assert all(c["name_te"] for c in cats)


def test_create_and_fetch_listing_with_fuzzed_location(db_client: TestClient) -> None:
    _, h = _user()
    created = _create(
        db_client, h, location={"lat": 38.84621, "lng": -77.30643}, category_id=None, city="Fairfax"
    )
    assert created["owner"]["display_name"] is None
    assert "email" not in created["owner"]
    assert created["location"] == {"lat": 38.85, "lng": -77.31}  # rounded for privacy

    fetched = db_client.get(f"/api/v1/listings/{created['id']}").json()
    assert fetched["title_en"] == "Teak dining table"


def test_geo_search_radius_and_sort(db_client: TestClient) -> None:
    _, h = _user()
    _create(db_client, h, title_en="Ashburn bike", location=ASHBURN)
    _create(db_client, h, title_en="Fairfax crib", location=FAIRFAX)
    _create(db_client, h, title_en="Richmond sofa", location=RICHMOND)

    r = db_client.get(
        "/api/v1/listings", params={**FAIRFAX, "radius_km": 40, "sort": "nearest"}
    ).json()
    titles = [i["title_en"] for i in r["items"]]
    assert titles == ["Fairfax crib", "Ashburn bike"]
    assert r["total"] == 2
    assert r["items"][1]["distance_km"] > 20


def test_search_filters(db_client: TestClient) -> None:
    _, h = _user()
    cats = {c["slug"]: c["id"] for c in db_client.get("/api/v1/categories").json()}
    _create(db_client, h, title_en="Silk saree", category_id=cats["ethnic-wear"])
    _create(db_client, h, listing_type="free", title_en="Moving boxes", price_cents=None)
    _create(db_client, h, title_en="100% cotton kurta", category_id=cats["ethnic-wear"])

    assert db_client.get("/api/v1/listings", params={"listing_type": "free"}).json()["total"] == 1
    assert (
        db_client.get("/api/v1/listings", params={"category": "ethnic-wear"}).json()["total"] == 2
    )
    assert db_client.get("/api/v1/listings", params={"q": "saree"}).json()["total"] == 1
    # LIKE wildcard in the query is treated literally
    assert db_client.get("/api/v1/listings", params={"q": "100%"}).json()["total"] == 1


def test_only_owner_can_edit_or_delete(db_client: TestClient) -> None:
    _, owner = _user("owner@example.com")
    _, other = _user("other@example.com")
    listing = _create(db_client, owner)
    url = f"/api/v1/listings/{listing['id']}"

    assert db_client.patch(url, json={"price_cents": 1}, headers=other).status_code == 403
    assert db_client.delete(url, headers=other).status_code == 403

    r = db_client.patch(url, json={"status": "sold"}, headers=owner)
    assert r.status_code == 200 and r.json()["status"] == "sold"

    assert db_client.delete(url, headers=owner).status_code == 204
    assert db_client.get(url).status_code == 404
    assert db_client.get("/api/v1/listings/mine", headers=owner).json() == []


def test_moderator_can_edit_any_listing(db_client: TestClient) -> None:
    _, owner = _user()
    mod_id, mod = _user("mod@example.com")
    listing = _create(db_client, owner)
    db_client.get("/api/v1/me", headers=mod)  # provision
    with get_sessionmaker()() as s:
        s.execute(update(Profile).where(Profile.id == mod_id).values(role=UserRole.MODERATOR))
        s.commit()
    r = db_client.patch(
        f"/api/v1/listings/{listing['id']}", json={"title_en": "Edited"}, headers=mod
    )
    assert r.status_code == 200


def test_banned_user_blocked(db_client: TestClient) -> None:
    uid, h = _user()
    db_client.get("/api/v1/me", headers=h)
    with get_sessionmaker()() as s:
        s.execute(update(Profile).where(Profile.id == uid).values(is_banned=True))
        s.commit()
    assert db_client.get("/api/v1/me", headers=h).status_code == 403


def test_unknown_category_rejected(db_client: TestClient) -> None:
    _, h = _user()
    r = db_client.post(
        "/api/v1/listings",
        json={"listing_type": "buy", "title_en": "Wanted: stroller", "category_id": 999999},
        headers=h,
    )
    assert r.status_code == 422
