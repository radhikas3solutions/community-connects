"""Verification of Supabase Auth access tokens (JWTs).

Supabase issues the token in the browser; the API only verifies it. The user's
role inside AskMitra lives in our own `profiles` table, never in the token,
so an admin can be promoted or demoted without re-issuing tokens.
"""

import uuid
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from app.core.config import Settings

ASYMMETRIC_ALGS = {"RS256", "ES256", "EdDSA"}


class AuthError(Exception):
    """Raised when a bearer token is missing, malformed, expired or untrusted."""


@dataclass(frozen=True)
class AuthUser:
    id: uuid.UUID
    email: str | None
    claims: dict[str, Any] = field(default_factory=dict)


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    # PyJWKClient caches keys and refetches on unknown `kid` (key rotation).
    return PyJWKClient(jwks_url, cache_keys=True, lifespan=600)


def decode_supabase_token(token: str, settings: Settings) -> AuthUser:
    try:
        header = jwt.get_unverified_header(token)
    except jwt.PyJWTError as exc:
        raise AuthError("Malformed token") from exc

    alg = header.get("alg")
    if alg == "HS256":
        if not settings.supabase_jwt_secret:
            raise AuthError("HS256 tokens are not accepted: SUPABASE_JWT_SECRET is not set")
        key: Any = settings.supabase_jwt_secret
    elif alg in ASYMMETRIC_ALGS:
        if not settings.supabase_issuer:
            raise AuthError("SUPABASE_URL is not configured")
        try:
            jwks = _jwks_client(f"{settings.supabase_issuer}/.well-known/jwks.json")
            key = jwks.get_signing_key_from_jwt(token).key
        except jwt.PyJWTError as exc:
            raise AuthError("Unable to resolve signing key") from exc
    else:
        raise AuthError(f"Unsupported token algorithm: {alg}")

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[alg],
            audience=settings.supabase_jwt_audience,
            issuer=settings.supabase_issuer,
            options={"require": ["exp", "sub", "aud"]},
            leeway=30,
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("Token expired") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("Invalid token") from exc

    try:
        user_id = uuid.UUID(claims["sub"])
    except ValueError as exc:
        raise AuthError("Invalid subject") from exc

    return AuthUser(id=user_id, email=claims.get("email"), claims=claims)
