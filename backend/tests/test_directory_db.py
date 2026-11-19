"""Directory: submit -> review -> public, contact privacy for individuals, search, menus."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.deps import get_menu_reader
from app.db.session import get_sessionmaker
from app.models import AIUsage, Category, Profile
from app.models.enums import UserRole
from app.services.ai_menu import ExtractedMenuItem, MenuError, MenuExtraction, MenuResult
from tests.conftest import auth_header, make_token
from tests.images import make_photo

pytestmark = pytest.mark.db

API = "/api/v1/businesses"


def _user(client: TestClient, role: UserRole = UserRole.USER) -> tuple[uuid.UUID, dict]:
    uid = uuid.uuid4()
    headers = auth_header(make_token(uid))
    assert client.get("/api/v1/me", headers=headers).status_code == 200  # provisions profile
    if role != UserRole.USER:
        with get_sessionmaker()() as db:
            db.execute(update(Profile).where(Profile.id == uid).values(role=role))
            db.commit()
    return uid, headers


def _category_id(slug: str) -> int:
    with get_sessionmaker()() as db:
        return db.scalars(select(Category.id).where(Category.slug == slug)).one()


def _restaurant(**overrides) -> dict:
    return {
        "kind": "business",
        "name": "Godavari Kitchen",
        "name_te": "గోదావరి కిచెన్",
        "category_id": _category_id("restaurants"),
        "description_en": "Andhra meals, biryanis and tiffins.",
        "phone": "(703) 555-0100",
        "address": "44 Main St",
        "city": "Ashburn",
        "zip_code": "20147",
        "hours": "Tue-Sun 11am-10pm",
        "languages": ["te", "en", "Hi"],
        **overrides,
    }


def _helper(**overrides) -> dict:
    return {
        "kind": "individual",
        "name": "Lakshmi",
        "category_id": _category_id("helpers"),
        "description_en": "Cooks Andhra meals, part-time.",
        "phone": "571-555-0199",
        "whatsapp": "+1 571 555 0199",
        "address": "12 Secret Ln",  # must never be stored for individuals
        "city": "Sterling",
        "service_area": "Sterling, Herndon",
        "languages": ["te"],
        "consent_confirmed": True,
        **overrides,
    }


def _create(client: TestClient, headers: dict, body: dict) -> dict:
    r = client.post(API, json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _approve(client: TestClient, staff: dict, entry_id: str, **extra) -> dict:
    r = client.post(f"{API}/{entry_id}/review", json={"action": "approve", **extra}, headers=staff)
    assert r.status_code == 200, r.text
    return r.json()


def test_member_submission_waits_for_review(db_client: TestClient) -> None:
    _, member = _user(db_client)
    _, staff = _user(db_client, UserRole.ADMIN)
    entry = _create(db_client, member, _restaurant())
    assert entry["status"] == "pending_review"
    assert entry["languages"] == ["te", "en", "hi"]
    assert entry["website"] is None and entry["can_edit"] is True

    # Not public yet
    assert db_client.get(API).json()["total"] == 0
    assert db_client.get(f"{API}/{entry['id']}").status_code == 404
    _, stranger = _user(db_client)
    assert db_client.get(f"{API}/{entry['id']}", headers=stranger).status_code == 404
    assert db_client.get(f"{API}/{entry['id']}", headers=member).status_code == 200

    # Only staff see the queue and approve
    assert db_client.get(f"{API}/review-queue", headers=member).status_code == 403
    queue = db_client.get(f"{API}/review-queue", headers=staff).json()
    assert [e["id"] for e in queue] == [entry["id"]]
    r = db_client.post(f"{API}/{entry['id']}/review", json={"action": "approve"}, headers=member)
    assert r.status_code == 403

    approved = _approve(db_client, staff, entry["id"], is_verified=True)
    assert approved["status"] == "active" and approved["is_verified"] is True
    public = db_client.get(f"{API}/{entry['id']}").json()
    assert public["phone"] == "(703) 555-0100" and public["address"] == "44 Main St"
    assert public["can_edit"] is False and public["contact_hidden"] is False
    assert db_client.get(API).json()["total"] == 1


def test_staff_entries_are_live_immediately(db_client: TestClient) -> None:
    _, staff = _user(db_client, UserRole.MODERATOR)
    entry = _create(db_client, staff, _restaurant())
    assert entry["status"] == "active"


def test_individual_contact_is_for_members_only(db_client: TestClient) -> None:
    _, member = _user(db_client)
    _, staff = _user(db_client, UserRole.ADMIN)
    entry = _create(db_client, member, _helper())
    assert entry["address"] is None
    _approve(db_client, staff, entry["id"])

    anon = db_client.get(f"{API}/{entry['id']}").json()
    assert anon["contact_hidden"] is True
    assert anon["phone"] is None and anon["whatsapp"] is None and anon["email"] is None
    assert anon["city"] == "Sterling"
    listed = db_client.get(API).json()["items"][0]
    assert listed["phone"] is None and listed["contact_hidden"] is True

    _, other = _user(db_client)
    seen = db_client.get(f"{API}/{entry['id']}", headers=other).json()
    assert seen["phone"] == "571-555-0199" and seen["contact_hidden"] is False

    # Editing can't add a home address either
    r = db_client.patch(f"{API}/{entry['id']}", json={"address": "1 Home Rd"}, headers=member)
    assert r.status_code == 200 and r.json()["address"] is None


def test_validation(db_client: TestClient) -> None:
    _, member = _user(db_client)
    cases = [
        (_helper(consent_confirmed=False), "agreed to be listed"),
        (_restaurant(phone=None), "way to contact"),
        (_restaurant(phone="call me maybe"), "valid phone"),
        (_restaurant(languages=["xx"]), "Unknown language"),
        (_restaurant(category_id=_category_id("furniture")), "directory category"),
    ]
    for body, fragment in cases:
        r = db_client.post(API, json=body, headers=member)
        assert r.status_code == 422, body
        assert fragment in r.text, r.text
    assert db_client.post(API, json=_restaurant()).status_code == 401

    entry = _create(db_client, member, _restaurant(website="godavari.example"))
    assert entry["website"] == "https://godavari.example"


def test_only_submitter_or_staff_can_edit(db_client: TestClient) -> None:
    _, member = _user(db_client)
    _, stranger = _user(db_client)
    _, staff = _user(db_client, UserRole.ADMIN)
    entry = _create(db_client, member, _restaurant())
    _approve(db_client, staff, entry["id"])

    r = db_client.patch(f"{API}/{entry['id']}", json={"hours": "Closed"}, headers=stranger)
    assert r.status_code == 403
    assert db_client.delete(f"{API}/{entry['id']}", headers=stranger).status_code == 403
    r = db_client.patch(f"{API}/{entry['id']}", json={"phone": None}, headers=member)
    assert r.status_code == 422  # would leave no way to contact them

    r = db_client.patch(f"{API}/{entry['id']}", json={"hours": "Daily 9-9"}, headers=staff)
    assert r.json()["hours"] == "Daily 9-9" and r.json()["status"] == "active"

    assert db_client.delete(f"{API}/{entry['id']}", headers=member).status_code == 204
    assert db_client.get(f"{API}/{entry['id']}").status_code == 404
    assert db_client.get(f"{API}/mine", headers=member).json() == []


def test_rejected_entry_is_resubmitted_by_editing(db_client: TestClient) -> None:
    _, member = _user(db_client)
    _, staff = _user(db_client, UserRole.ADMIN)
    entry = _create(db_client, member, _restaurant())
    r = db_client.post(
        f"{API}/{entry['id']}/review",
        json={"action": "reject", "note": "Please add the street address"},
        headers=staff,
    )
    assert r.json()["status"] == "rejected"

    mine = db_client.get(f"{API}/mine", headers=member).json()
    assert mine[0]["review_note"] == "Please add the street address"
    r = db_client.patch(f"{API}/{entry['id']}", json={"address": "45 Main St"}, headers=member)
    assert r.json()["status"] == "pending_review"


def test_search_filters(db_client: TestClient) -> None:
    _, staff = _user(db_client, UserRole.ADMIN)
    _create(db_client, staff, _restaurant())
    _create(
        db_client,
        staff,
        _restaurant(
            name="Dulles Dosa House",
            name_te="డల్లెస్ దోశ హౌస్",
            description_en="Crispy dosas and filter coffee.",
            languages=["en"],
            city="Chantilly",
        ),
    )
    _create(db_client, staff, _helper())

    def names(**params) -> list[str]:
        return [e["name"] for e in db_client.get(API, params=params).json()["items"]]

    assert names() == ["Dulles Dosa House", "Godavari Kitchen", "Lakshmi"]
    assert names(category="helpers") == ["Lakshmi"]
    assert names(kind="business") == ["Dulles Dosa House", "Godavari Kitchen"]
    assert names(language="te") == ["Godavari Kitchen", "Lakshmi"]
    assert names(city="herndon") == ["Lakshmi"]  # matches the service area
    assert names(q="dosa") == ["Dulles Dosa House"]
    assert names(q="biryani") == ["Godavari Kitchen"]  # stemmed description match
    assert names(q="గోదావరి") == ["Godavari Kitchen"]  # Telugu name
    assert db_client.get(API, params={"language": "xx"}).status_code == 422


# ---------------------------------------------------------------- menu


class FakeMenuReader:
    def __init__(self, extraction: MenuExtraction | None = None, error: MenuError | None = None):
        self.extraction, self.error, self.calls = extraction, error, []

    def read(self, images: list[bytes], business_name: str) -> MenuResult:
        self.calls.append((len(images), business_name))
        if self.error:
            raise self.error
        assert self.extraction is not None
        return MenuResult(
            extraction=self.extraction,
            model="claude-opus-5-5",
            request_id="req_fake",
            input_tokens=3000,
            output_tokens=900,
            cache_read_tokens=0,
            latency_ms=4000,
        )


MENU = MenuExtraction(
    problem="none",
    items=[
        ExtractedMenuItem(
            section="Biryanis",
            name="Chicken Dum Biryani",
            name_te="చికెన్ దమ్ బిర్యానీ",
            description=None,
            price_usd=15.99,
            is_vegetarian=False,
        ),
        ExtractedMenuItem(
            section="Tiffins",
            name="  Masala   Dosa ",
            name_te=None,
            description="With sambar and chutney",
            price_usd=None,
            is_vegetarian=True,
        ),
        ExtractedMenuItem(
            section=None,
            name="   ",
            name_te=None,
            description=None,
            price_usd=1,
            is_vegetarian=None,
        ),
    ],
)


@pytest.fixture
def menu_client(db_client: TestClient) -> Iterator[tuple[TestClient, FakeMenuReader]]:
    reader = FakeMenuReader(MENU)
    db_client.app.dependency_overrides[get_menu_reader] = lambda: reader  # type: ignore[attr-defined]
    yield db_client, reader
    db_client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _menu_photos(n: int = 2) -> list:
    return [("photos", (f"m{i}.jpg", make_photo(), "image/jpeg")) for i in range(n)]


def test_menu_photos_become_a_suggestion_then_saved_menu(
    menu_client: tuple[TestClient, FakeMenuReader],
) -> None:
    client, reader = menu_client
    member_id, member = _user(client)
    _, stranger = _user(client)
    entry = _create(client, member, _restaurant())
    url = f"{API}/{entry['id']}/menu/read-photos"

    assert client.post(url, files=_menu_photos(), headers=stranger).status_code == 403
    r = client.post(url, files=_menu_photos(), headers=member)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert reader.calls == [(2, "Godavari Kitchen")]
    assert [i["name"] for i in items] == ["Chicken Dum Biryani", "Masala Dosa"]  # blank dropped
    assert items[0]["price_cents"] == 1599 and items[0]["is_vegetarian"] is False
    assert items[1]["price_cents"] is None and items[0]["id"] is None

    # Nothing saved until the editor confirms
    assert client.get(f"{API}/{entry['id']}", headers=member).json()["menu"] == []
    with get_sessionmaker()() as db:
        usage = db.scalars(select(AIUsage).where(AIUsage.profile_id == member_id)).one()
        assert (usage.feature, usage.outcome, str(usage.business_id)) == (
            "read_menu",
            "ok",
            entry["id"],
        )

    items[1]["price_cents"] = 1099
    r = client.put(f"{API}/{entry['id']}/menu", json={"items": items}, headers=member)
    assert r.status_code == 200, r.text
    menu = r.json()["menu"]
    assert [(m["name"], m["price_cents"]) for m in menu] == [
        ("Chicken Dum Biryani", 1599),
        ("Masala Dosa", 1099),
    ]
    assert all(m["id"] for m in menu)

    # Replacing again keeps only the new list, in order
    r = client.put(
        f"{API}/{entry['id']}/menu", json={"items": [{"name": "Filter Coffee"}]}, headers=member
    )
    assert [m["name"] for m in r.json()["menu"]] == ["Filter Coffee"]
    r = client.put(f"{API}/{entry['id']}/menu", json={"items": []}, headers=stranger)
    assert r.status_code == 403


def test_menu_reader_problems(menu_client: tuple[TestClient, FakeMenuReader]) -> None:
    client, reader = menu_client
    _, member = _user(client)
    entry = _create(client, member, _restaurant())
    url = f"{API}/{entry['id']}/menu/read-photos"

    reader.extraction = MenuExtraction(problem="not_a_menu", items=[])
    r = client.post(url, files=_menu_photos(1), headers=member)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "not_a_menu"

    reader.error = MenuError("AI service error")
    r = client.post(url, files=_menu_photos(1), headers=member)
    assert r.status_code == 502
