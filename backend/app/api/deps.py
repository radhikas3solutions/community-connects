from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import AuthError, AuthUser, decode_supabase_token
from app.db.session import get_db
from app.models import Profile
from app.models.enums import UserRole

bearer = HTTPBearer(auto_error=False)


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")
    try:
        return decode_supabase_token(creds.credentials, settings)
    except AuthError as exc:
        raise _unauthorized(str(exc)) from exc


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
    settings: Settings = Depends(get_settings),
) -> AuthUser | None:
    if creds is None:
        return None
    try:
        return decode_supabase_token(creds.credentials, settings)
    except AuthError:
        return None


def get_current_profile(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    """Return the caller's profile, creating it on first sight (just-in-time provisioning)."""
    profile = db.get(Profile, user.id)
    if profile is None:
        meta = user.claims.get("user_metadata") or {}
        stmt = (
            insert(Profile)
            .values(
                id=user.id,
                email=user.email,
                display_name=(meta.get("full_name") or meta.get("name") or None),
                avatar_url=meta.get("avatar_url"),
            )
            .on_conflict_do_nothing(index_elements=[Profile.id])
        )
        db.execute(stmt)
        db.commit()
        profile = db.get(Profile, user.id)
        assert profile is not None
    if profile.is_banned:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account suspended")
    return profile


def require_roles(*roles: UserRole) -> Callable[[Profile], Profile]:
    def checker(profile: Profile = Depends(get_current_profile)) -> Profile:
        if profile.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
        return profile

    return checker


require_staff = require_roles(UserRole.MODERATOR, UserRole.ADMIN)
require_admin = require_roles(UserRole.ADMIN)
