"""OpenStreetMap restaurant import: parsing, dedupe, re-import, attribution, staff only."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.deps import get_osm_client
from app.db.session import get_sessionmaker
from app.models import Business, Profile
from app.models.enums import DirectoryStatus, UserRole
from app.services.osm import Area, OsmError, describe, nearest_town, places_from_elements
from tests.conftest import auth_header, make_token

pytestmark = pytest.mark.db

URL = "/api/v1/admin/import/osm"


def _node(id_: int, lat: float, lon: float, **tags: str) -> dict[str, Any]:
    return {"type": "node", "id": id_, "lat": lat, "lon": lon, "tags": tags}


ELEMENTS = [
    _node(
        1,
        39.03,
        -77.48,
        **{
            "amenity": "restaurant",
            "name": "Persis Biryani Indian Grill",
            "cuisine": "indian;biryani",
            "addr:housenumber": "44050",
            "addr:street": "Ashburn Shopping Plaza",
            "addr:unit": "191",
            "addr:city": "Ashburn",
            "addr:postcode": "20147-1234",
            "phone": "+1 703-723-0040",
            "opening_hours": "Tu-Su 11:30-21:30; Mo off",
            "diet:vegetarian": "yes",
            "delivery": "yes",
            "website": "persisbiryani.com",
        },
    ),  # fmt: skip
    # The same restaurant mapped again as a building outline -> one entry.
    {
        "type": "way",
        "id": 2,
        "center": {"lat": 39.03, "lon": -77.48},
        "tags": {
            "amenity": "restaurant",
            "name": "Persis Biryani Indian Grill",
            "addr:housenumber": "44050",
            "addr:street": "Ashburn Shopping Plaza",
            "addr:unit": "191",
        },
    },  # fmt: skip
    # No town, misspelled town -> nearest town centre.
    _node(3, 38.976, -77.640, amenity="cafe", name="Aldie Coffee"),
    _node(4, 38.971, -77.387, amenity="fast_food", name="Chowrastha", **{"addr:city": "Herdon"}),
    # No name; a bar; inside the Dulles terminals -> skipped.
    _node(5, 39.0, -77.5, amenity="restaurant"),
    _node(6, 39.0, -77.5, amenity="bar", name="A Bar"),
    _node(7, 38.953, -77.448, amenity="fast_food", name="Airport Burger"),
]


class FakeOsm:
    def __init__(self) -> None:
        self.elements = ELEMENTS
        self.error = False
        self.calls: list[str] = []

    def fetch(self, area: Area) -> list[dict[str, Any]]:
        self.calls.append(area.key)
        if self.error:
            raise OsmError("OpenStreetMap is busy right now.")
        return self.elements


@pytest.fixture
def osm(db_client: TestClient) -> Iterator[tuple[TestClient, FakeOsm]]:
    fake = FakeOsm()
    db_client.app.dependency_overrides[get_osm_client] = lambda: fake  # type: ignore[attr-defined]
    yield db_client, fake
    db_client.app.dependency_overrides.clear()  # type: ignore[attr-defined]


def _user(client: TestClient, role: UserRole = UserRole.USER) -> dict:
    uid = uuid.uuid4()
    headers = auth_header(make_token(uid))
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    if role != UserRole.USER:
        with get_sessionmaker()() as db:
            db.execute(update(Profile).where(Profile.id == uid).values(role=role))
            db.commit()
    return headers


def test_parsing() -> None:
    places = {p.key: p for p in places_from_elements(ELEMENTS)}
    assert set(places) == {"node/1", "way/2", "node/3", "node/4"}
    persis = places["node/1"]
    assert persis.address == "44050 Ashburn Shopping Plaza #191"
    assert (persis.city, persis.zip_code, persis.phone) == ("Ashburn", "20147", "703-723-0040")
    assert persis.website == "https://persisbiryani.com"
    assert persis.hours == "Tue-Sun 11:30-21:30, Mon off"
    assert persis.description.startswith(
        "Restaurant · Indian, Biryani. Vegetarian options, Delivery."
    )
    assert places["node/3"].city == "Aldie"
    assert places["node/4"].city == "Herndon"
    assert nearest_town(39.115, -77.565) == "Leesburg"
    assert "Part of Dunkin'" in describe({"amenity": "cafe", "name": "DD", "brand": "Dunkin'"})


def test_staff_only(osm: tuple[TestClient, FakeOsm]) -> None:
    client, _ = osm
    assert client.post(URL, json={"area": "loudoun"}).status_code == 401
    assert client.post(URL, json={"area": "loudoun"}, headers=_user(client)).status_code == 403


def test_import_reimport_and_attribution(osm: tuple[TestClient, FakeOsm]) -> None:
    client, fake = osm
    staff = _user(client, UserRole.ADMIN)
    assert {a["key"] for a in client.get(URL, headers=staff).json()["areas"]} >= {"loudoun"}

    r = client.post(URL, json={"area": "loudoun"}, headers=staff)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "area": "loudoun",
        "places": 4,
        "created": 3,
        "updated": 0,
        "already_listed": 1,  # the building outline of Persis
        "skipped_removed": 0,
    }
    assert fake.calls == ["loudoun"]

    found = client.get("/api/v1/businesses", params={"q": "biryani", "city": "Ashburn"}).json()
    persis = found["items"][0]
    assert persis["name"] == "Persis Biryani Indian Grill"
    assert persis["category"]["slug"] == "restaurants" and persis["source"] == "osm"
    assert persis["source_url"] == "https://www.openstreetmap.org/node/1"
    assert persis["is_verified"] is False and persis["whatsapp"] is None

    with get_sessionmaker()() as db:
        db.execute(
            update(Business)
            .where(Business.name == "Aldie Coffee")
            .values(status=DirectoryStatus.REMOVED)
        )
        db.commit()
    r = client.post(URL, json={"area": "loudoun"}, headers=staff).json()
    assert (r["created"], r["updated"], r["skipped_removed"]) == (0, 2, 1)
    with get_sessionmaker()() as db:
        assert len(db.scalars(select(Business).where(Business.source == "osm")).all()) == 3


def test_errors(osm: tuple[TestClient, FakeOsm]) -> None:
    client, fake = osm
    staff = _user(client, UserRole.MODERATOR)
    assert client.post(URL, json={"area": "mars"}, headers=staff).status_code == 422
    fake.error = True
    r = client.post(URL, json={"area": "loudoun"}, headers=staff)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "osm_unavailable"
