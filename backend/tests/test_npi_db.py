"""NPI Registry import: practice addresses only, grouping, re-import, staff only."""

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.api.deps import get_npi_client
from app.db.session import get_sessionmaker
from app.models import Business, Profile
from app.models.enums import DirectoryStatus, UserRole
from app.services.npi import PRESETS, NpiError, describe, practices_from_results
from tests.conftest import auth_header, make_token

pytestmark = pytest.mark.db

URL = "/api/v1/admin/import/npi"


def _address(purpose: str, line: str, city: str, zip9: str, phone: str | None, state="VA") -> dict:
    a = {"address_purpose": purpose, "address_1": line, "city": city, "postal_code": zip9,
         "state": state}  # fmt: skip
    if phone:
        a["telephone_number"] = phone
    return a


def _org(
    npi: str,
    name: str,
    location: dict,
    *,
    dba: str | None = None,
    mailing: dict | None = None,
    tax: str = "Dentist",
) -> dict:
    return {
        "number": npi,
        "enumeration_type": "NPI-2",
        "basic": {"organization_name": name, "status": "A"},
        "other_names": [{"type": "Doing Business As", "organization_name": dba}] if dba else [],
        "addresses": [location, *([mailing] if mailing else [])],
        "taxonomies": [{"desc": tax, "primary": True}],
    }


def _person(
    npi: str,
    first: str,
    last: str,
    cred: str,
    location: dict,
    *,
    taxes: tuple[str, ...] = ("Dentist, General Practice",),
    status: str = "A",
) -> dict:
    return {
        "number": npi,
        "enumeration_type": "NPI-1",
        "basic": {"first_name": first, "last_name": last, "credential": cred, "status": status},
        "other_names": [],
        "addresses": [location],
        "taxonomies": [{"desc": t, "primary": i == 0} for i, t in enumerate(taxes)],
    }


ALDIE_SMILES = _address(
    "LOCATION", "24560 SOUTHPOINT DR # 370", "ALDIE", "201053510", "571-463-1184"
)
RECORDS = [
    # Practice + its dentist (same phone) -> one entry named after the practice.
    _org("1801633359", "ALDIE SMILES, PLLC", ALDIE_SMILES),
    _person("1000000001", "EDWARD", "PARK", "D.M.D", ALDIE_SMILES),
    # Practice in Maryland; only the MAILING address is in Aldie (a home) -> skipped.
    _org(
        "1588261085",
        "ACORA DENTAL, LLC",
        _address("LOCATION", "85 HIGH ST", "WALDORF", "206022150", "301-645-6004", state="MD"),
        mailing=_address("MAILING", "41667 BLUE GRAMA CIR", "ALDIE", "201055512", None),
    ),
    # Solo dentist, hyphenated name, DBA-less.
    _person(
        "1000000002",
        "HONG",
        "CAO-ROTHWELL",
        "DMD",
        _address("LOCATION", "42010 VILLAGE CENTER PLZ", "STONE RIDGE", "201051234", "7033270441"),
    ),  # fmt: skip
    # Matches "Dentist" only through an excluded specialty -> skipped.
    _person(
        "1000000003",
        "BONITA",
        "NEIGHBORS",
        "DDS",
        _address("LOCATION", "1 HOME LN", "ALDIE", "20105", "734-646-6694"),
        taxes=("Dentist, Dental Public Health",),
    ),  # fmt: skip
    # Primary specialty is something else, but a dentist taxonomy matches.
    _person(
        "1000000004",
        "MARK",
        "ARMANIOUS",
        "DMD",
        _address("LOCATION", "24600 MILLSTREAM DR", "ALDIE", "20105", "703-327-5655"),
        taxes=("Counselor, Mental Health", "Dentist, Oral and Maxillofacial Surgery"),
    ),  # fmt: skip
    # Deactivated -> skipped.
    _person(
        "1000000005",
        "OLD",
        "RECORD",
        "DDS",
        _address("LOCATION", "2 OLD RD", "ALDIE", "20105", "703-000-0000"),
        status="D",
    ),  # fmt: skip
    # Organization with a "doing business as" name.
    _org(
        "1000000006",
        "BROWN FRANKENBERRY PC",
        _address("LOCATION", "24600 MILLSTREAM DR STE 101", "STONE RIDGE", "20105", "202-258-1225"),
        dba="STONE RIDGE ORTHODONTICS",
        tax="Dentist, Orthodontics and Dentofacial Orthopedics",
    ),  # fmt: skip
]


class FakeNpi:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = RECORDS
        self.error = False
        self.calls: list[tuple[str, str]] = []

    def search(self, postal_code: str, taxonomy: str) -> list[dict[str, Any]]:
        self.calls.append((postal_code, taxonomy))
        if self.error:
            raise NpiError("The NPI Registry could not be reached")
        return self.records


@pytest.fixture
def npi(db_client: TestClient) -> Iterator[tuple[TestClient, FakeNpi]]:
    fake = FakeNpi()
    db_client.app.dependency_overrides[get_npi_client] = lambda: fake  # type: ignore[attr-defined]
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


def test_grouping_and_filtering() -> None:
    practices = practices_from_results(RECORDS, "20105", PRESETS["dentists"])
    by_name = {p.name: p for p in practices}
    assert set(by_name) == {
        "Aldie Smiles",
        "Dr. Hong Cao-Rothwell, DMD",
        "Dr. Mark Armanious, DMD",
        "Stone Ridge Orthodontics",
    }
    smiles = by_name["Aldie Smiles"]
    assert smiles.providers == ["Dr. Edward Park, DMD"]
    assert smiles.address == "24560 Southpoint Dr # 370" and smiles.city == "Aldie"
    assert smiles.phone == "571-463-1184" and smiles.key == "20105:5714631184"
    assert by_name["Dr. Mark Armanious, DMD"].specialties == [
        "Dentist, Oral and Maxillofacial Surgery"
    ]
    assert practices_from_results(RECORDS, "20152", PRESETS["dentists"]) == []


def test_person_names() -> None:
    from app.services.npi import _person_name

    assert _person_name({"first_name": "BROOKE", "last_name": "BOKOR", "credential": "MD,MPH"}) == (
        "Dr. Brooke Bokor, MD, MPH"
    )
    assert _person_name(
        {"first_name": "DENA", "last_name": "TAYLOR", "credential": "R.N., CPNP"}
    ) == ("Dena Taylor, RN, CPNP")
    assert _person_name({"first_name": "ANA", "last_name": "LI"}) == "Ana Li"


def test_describe_skips_generic_specialty_and_own_name() -> None:
    text = describe(
        ["Dentist", "Dentist, Orthodontics"], ["Dr. A, DDS", "Dr. B, DDS"], "Dr. A, DDS"
    )
    assert text.startswith("Dentist, Orthodontics. Providers: Dr. B, DDS.")
    assert "NPI Registry" in text


def test_staff_only(npi: tuple[TestClient, FakeNpi]) -> None:
    client, _ = npi
    body = {"postal_code": "20105", "preset": "dentists"}
    assert client.post(URL, json=body).status_code == 401
    assert client.post(URL, json=body, headers=_user(client)).status_code == 403
    assert client.get(URL, headers=_user(client)).status_code == 403


def test_import_reimport_and_respect_removals(npi: tuple[TestClient, FakeNpi]) -> None:
    client, fake = npi
    staff = _user(client, UserRole.ADMIN)
    options = client.get(URL, headers=staff).json()
    assert (
        "dentists" in {p["key"] for p in options["presets"]} and "20105" in options["default_zips"]
    )

    # A member already listed Dr. Armanious's practice (same phone, different format).
    member = _user(client)
    r = client.post(
        "/api/v1/businesses",
        json={"kind": "business", "name": "Armanious Oral Surgery", "phone": "(703) 327-5655"},
        headers=member,
    )
    assert r.status_code == 201

    r = client.post(URL, json={"postal_code": "20105", "preset": "dentists"}, headers=staff)
    assert r.status_code == 200, r.text
    assert r.json() == {
        "postal_code": "20105",
        "preset": "dentists",
        "records": len(RECORDS),
        "practices": 4,
        "created": 3,
        "updated": 0,
        "already_listed": 1,
        "skipped_removed": 0,
    }
    assert fake.calls == [("20105", "Dentist")]

    # Imported entries are live, unverified, labelled, and searchable as "dentist".
    found = client.get("/api/v1/businesses", params={"q": "dentist", "city": "Aldie"}).json()
    smiles = next(b for b in found["items"] if b["name"] == "Aldie Smiles")
    assert smiles["source"] == "npi" and smiles["is_verified"] is False
    assert smiles["category"]["slug"] == "doctors"
    assert smiles["address"] == "24560 Southpoint Dr # 370"
    assert "Dr. Edward Park, DMD" in smiles["description_en"]

    # Re-import: updates, no duplicates; a removed entry stays removed.
    with get_sessionmaker()() as db:
        db.execute(
            update(Business)
            .where(Business.name == "Dr. Hong Cao-Rothwell, DMD")
            .values(status=DirectoryStatus.REMOVED)
        )
        db.commit()
    r = client.post(URL, json={"postal_code": "20105", "preset": "dentists"}, headers=staff)
    assert r.json()["created"] == 0 and r.json()["updated"] == 2
    assert r.json()["skipped_removed"] == 1
    with get_sessionmaker()() as db:
        assert db.scalar(select(Business).where(Business.name == "Aldie Smiles")) is not None
        assert len(db.scalars(select(Business).where(Business.source == "npi")).all()) == 3


def test_errors(npi: tuple[TestClient, FakeNpi]) -> None:
    client, fake = npi
    staff = _user(client, UserRole.MODERATOR)
    assert (
        client.post(
            URL, json={"postal_code": "2010", "preset": "dentists"}, headers=staff
        ).status_code
        == 422
    )
    assert (
        client.post(URL, json={"postal_code": "20105", "preset": "vets"}, headers=staff).status_code
        == 422
    )
    fake.error = True
    r = client.post(URL, json={"postal_code": "20105", "preset": "dentists"}, headers=staff)
    assert r.status_code == 502 and r.json()["detail"]["code"] == "npi_unavailable"
