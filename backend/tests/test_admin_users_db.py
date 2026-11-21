"""Registration details land on the profile; only admins manage members' access."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update

from app.db.session import get_sessionmaker
from app.models import Profile
from app.models.enums import UserRole
from tests.conftest import auth_header, make_token

pytestmark = pytest.mark.db

URL = "/api/v1/admin/users"
SIGNUP = {
    "first_name": " Lakshmi ",
    "last_name": "Rao",
    "phone": "703-555-0142",
    "whatsapp": "+91 77023 45678",
}


def _member(
    client: TestClient, role: UserRole = UserRole.USER, **meta: str
) -> tuple[uuid.UUID, dict]:
    uid = uuid.uuid4()
    headers = auth_header(make_token(uid, email=f"{uid.hex[:8]}@example.com", user_metadata=meta))
    assert client.get("/api/v1/me", headers=headers).status_code == 200
    if role != UserRole.USER:
        with get_sessionmaker()() as db:
            db.execute(update(Profile).where(Profile.id == uid).values(role=role))
            db.commit()
    return uid, headers


def test_registration_details_on_profile(db_client: TestClient) -> None:
    _, headers = _member(db_client, **SIGNUP)
    me = db_client.get("/api/v1/me", headers=headers).json()
    assert (me["first_name"], me["last_name"], me["display_name"]) == (
        "Lakshmi",
        "Rao",
        "Lakshmi Rao",
    )
    assert (me["phone"], me["whatsapp"], me["whatsapp_opt_in"]) == (
        "+17035550142",
        "+917702345678",
        True,
    )

    # Members fix their numbers later, in any country's format; junk is refused.
    r = db_client.patch(
        "/api/v1/me", json={"phone": "+44 20 7946 0958", "whatsapp": ""}, headers=headers
    )
    assert (r.json()["phone"], r.json()["whatsapp"]) == ("+442079460958", None)
    assert (
        db_client.patch("/api/v1/me", json={"phone": "12345"}, headers=headers).status_code == 422
    )


def test_normalize_phone() -> None:
    from app.core.phone import normalize_phone

    assert normalize_phone("(703) 555-0123") == "+17035550123"
    assert normalize_phone("1 703 555 0123") == "+17035550123"
    assert normalize_phone("+91 98765 43210") == "+919876543210"
    assert normalize_phone("0044 20 7946 0958") == "+442079460958"
    assert normalize_phone("98765 43210 9") is None  # no country code and not US-length
    assert normalize_phone("+12") is None and normalize_phone("") is None


def test_admin_only(db_client: TestClient) -> None:
    uid, user = _member(db_client)
    _, moderator = _member(db_client, UserRole.MODERATOR)
    assert db_client.get(URL).status_code == 401
    assert db_client.get(URL, headers=user).status_code == 403
    assert db_client.get(URL, headers=moderator).status_code == 403
    r = db_client.patch(f"{URL}/{uid}", json={"role": "admin"}, headers=user)
    assert r.status_code == 403


def test_admin_changes_role_and_suspends(db_client: TestClient) -> None:
    admin_id, admin = _member(db_client, UserRole.ADMIN)
    uid, user = _member(db_client, **SIGNUP)

    found = db_client.get(URL, params={"q": "lakshmi rao"}, headers=admin).json()
    assert [u["id"] for u in found] == [str(uid)] and found[0]["is_banned"] is False
    for number in ("(703) 555-0142", "77023 45678"):  # by phone, then by WhatsApp
        found = db_client.get(URL, params={"q": number}, headers=admin).json()
        assert [u["id"] for u in found] == [str(uid)], number

    r = db_client.patch(f"{URL}/{uid}", json={"role": "moderator"}, headers=admin)
    assert r.status_code == 200 and r.json()["role"] == "moderator"

    assert (
        db_client.patch(f"{URL}/{uid}", json={"is_banned": True}, headers=admin).status_code == 200
    )
    assert db_client.get("/api/v1/me", headers=user).status_code == 403
    assert (
        db_client.patch(f"{URL}/{uid}", json={"is_banned": False}, headers=admin).status_code == 200
    )
    assert db_client.get("/api/v1/me", headers=user).status_code == 200

    # Admins can't demote or suspend themselves; bad roles are rejected.
    r = db_client.patch(f"{URL}/{admin_id}", json={"role": "user"}, headers=admin)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "self_change"
    assert db_client.patch(f"{URL}/{uid}", json={"role": "owner"}, headers=admin).status_code == 422
    assert (
        db_client.patch(f"{URL}/{uuid.uuid4()}", json={"role": "user"}, headers=admin).status_code
        == 404
    )
