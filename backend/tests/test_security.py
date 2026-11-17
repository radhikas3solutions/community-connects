import time
import uuid

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from app.core import security
from app.core.config import Settings
from app.core.security import AuthError, decode_supabase_token
from tests.conftest import TEST_JWT_SECRET, make_token


def hs_settings(**kw) -> Settings:
    return Settings(supabase_jwt_secret=TEST_JWT_SECRET, supabase_url="", **kw)


def test_valid_hs256_token() -> None:
    uid = uuid.uuid4()
    user = decode_supabase_token(make_token(uid, email="a@b.co"), hs_settings())
    assert user.id == uid
    assert user.email == "a@b.co"


def test_expired_token_rejected() -> None:
    with pytest.raises(AuthError, match="expired"):
        decode_supabase_token(make_token(exp_delta=-3600), hs_settings())


def test_wrong_secret_rejected() -> None:
    with pytest.raises(AuthError):
        decode_supabase_token(make_token(secret="x" * 40), hs_settings())


def test_wrong_audience_rejected() -> None:
    with pytest.raises(AuthError):
        decode_supabase_token(make_token(aud="anon"), hs_settings())


def test_hs256_refused_without_secret() -> None:
    with pytest.raises(AuthError, match="SUPABASE_JWT_SECRET"):
        decode_supabase_token(make_token(), Settings(supabase_jwt_secret="", supabase_url=""))


def test_alg_none_rejected() -> None:
    token = jwt.encode({"sub": str(uuid.uuid4()), "aud": "authenticated"}, None, algorithm="none")
    with pytest.raises(AuthError, match="Unsupported"):
        decode_supabase_token(token, hs_settings())


def test_non_uuid_subject_rejected() -> None:
    with pytest.raises(AuthError, match="subject"):
        decode_supabase_token(make_token("not-a-uuid"), hs_settings())


def test_issuer_enforced_when_supabase_url_set() -> None:
    settings = Settings(supabase_jwt_secret=TEST_JWT_SECRET, supabase_url="https://p.supabase.co")
    good = make_token(iss="https://p.supabase.co/auth/v1")
    assert decode_supabase_token(good, settings)
    with pytest.raises(AuthError):
        decode_supabase_token(make_token(iss="https://evil.example/auth/v1"), settings)


def test_es256_token_via_jwks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asymmetric signing keys (Supabase's current default) are verified through JWKS."""
    private_key = ec.generate_private_key(ec.SECP256R1())
    url = "https://p.supabase.co"

    class FakeJWKS:
        def get_signing_key_from_jwt(self, token: str):  # noqa: ANN201
            return type("K", (), {"key": private_key.public_key()})()

    monkeypatch.setattr(security, "_jwks_client", lambda _url: FakeJWKS())
    uid = uuid.uuid4()
    now = int(time.time())
    token = jwt.encode(
        {"sub": str(uid), "aud": "authenticated", "iss": f"{url}/auth/v1", "exp": now + 60},
        private_key,
        algorithm="ES256",
        headers={"kid": "k1"},
    )
    user = decode_supabase_token(token, Settings(supabase_url=url, supabase_jwt_secret=""))
    assert user.id == uid
