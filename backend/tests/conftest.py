import os
import time
import uuid
from collections.abc import Iterator
from typing import Any

import jwt
import pytest

# Force deterministic auth config for the test process (beats any .env values).
TEST_JWT_SECRET = "test-secret-that-is-at-least-32-bytes-long!!"
os.environ["SUPABASE_JWT_SECRET"] = TEST_JWT_SECRET
os.environ["SUPABASE_URL"] = ""
os.environ["ENVIRONMENT"] = "test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
if TEST_DATABASE_URL:
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.main import create_app  # noqa: E402

get_settings.cache_clear()


def make_token(
    sub: uuid.UUID | str | None = None,
    *,
    email: str = "user@example.com",
    secret: str = TEST_JWT_SECRET,
    exp_delta: int = 3600,
    aud: str = "authenticated",
    **extra: Any,
) -> str:
    now = int(time.time())
    claims = {
        "sub": str(sub or uuid.uuid4()),
        "email": email,
        "aud": aud,
        "role": "authenticated",
        "iat": now,
        "exp": now + exp_delta,
        **extra,
    }
    return jwt.encode(claims, secret, algorithm="HS256")


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as c:
        yield c


# ---------------------------------------------------------------- database fixtures


@pytest.fixture(scope="session")
def migrated_db() -> Iterator[None]:
    if not TEST_DATABASE_URL:
        pytest.skip("TEST_DATABASE_URL not set; skipping PostGIS integration tests")
    from alembic import command
    from alembic.config import Config

    from app.db.session import get_engine, get_sessionmaker
    from app.seed import seed_categories

    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    here = os.path.dirname(os.path.dirname(__file__))
    cfg = Config(os.path.join(here, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(here, "alembic"))
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    seed_categories()
    yield


@pytest.fixture
def db_client(migrated_db: None) -> Iterator[TestClient]:
    from sqlalchemy import text

    from app.db.session import get_engine

    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE listings, profiles CASCADE"))
    with TestClient(create_app()) as c:
        yield c
