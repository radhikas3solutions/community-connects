from fastapi.testclient import TestClient

from tests.conftest import auth_header, make_token


def test_health(client: TestClient) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_me_requires_auth(client: TestClient) -> None:
    r = client.get("/api/v1/me")
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


def test_me_rejects_bad_token(client: TestClient) -> None:
    r = client.get("/api/v1/me", headers=auth_header("garbage"))
    assert r.status_code == 401


def test_me_rejects_expired_token(client: TestClient) -> None:
    r = client.get("/api/v1/me", headers=auth_header(make_token(exp_delta=-100)))
    assert r.status_code == 401
    assert r.json()["detail"] == "Token expired"


def test_create_listing_requires_auth(client: TestClient) -> None:
    r = client.post("/api/v1/listings", json={"listing_type": "free", "title_en": "Desk"})
    assert r.status_code == 401


def test_cors_preflight(client: TestClient) -> None:
    r = client.options(
        "/api/v1/categories",
        headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
