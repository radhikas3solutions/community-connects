from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.security import AuthError, AuthUser, decode_supabase_token
from app.db.session import get_db
from app.models import Profile
from app.models.enums import UserRole
from app.services.ai_intake import ClaudeIntakeAssistant, IntakeAssistant
from app.services.ai_listing import ClaudeListingDrafter, ListingDrafter
from app.services.ai_menu import ClaudeMenuReader, MenuReader
from app.services.ai_search import ClaudeSearchAgent, SearchAgent
from app.services.npi import HttpNpiClient, NpiClient
from app.services.storage import PhotoStorage, SupabaseStorage

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


# ---------------------------------------------------------------- services
# Tests override these with in-memory fakes via app.dependency_overrides.


@lru_cache
def _supabase_storage() -> SupabaseStorage:
    return SupabaseStorage(get_settings())


def get_storage(settings: Settings = Depends(get_settings)) -> PhotoStorage | None:
    """Photo storage, or None when it isn't configured (listings then render without photos)."""
    return _supabase_storage() if settings.storage_configured else None


def require_storage(storage: PhotoStorage | None = Depends(get_storage)) -> PhotoStorage:
    if storage is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "storage_unavailable", "message": "Photo uploads are not configured"},
        )
    return storage


@lru_cache
def _claude_drafter() -> ClaudeListingDrafter:
    return ClaudeListingDrafter(get_settings())


def get_drafter(settings: Settings = Depends(get_settings)) -> ListingDrafter:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_unavailable", "message": "AI drafting is not configured"},
        )
    return _claude_drafter()


@lru_cache
def _claude_menu_reader() -> ClaudeMenuReader:
    return ClaudeMenuReader(get_settings())


def get_menu_reader(settings: Settings = Depends(get_settings)) -> MenuReader:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_unavailable", "message": "AI menu reading is not configured"},
        )
    return _claude_menu_reader()


@lru_cache
def _claude_intake_assistant() -> ClaudeIntakeAssistant:
    return ClaudeIntakeAssistant(get_settings())


def get_intake_assistant(settings: Settings = Depends(get_settings)) -> IntakeAssistant:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_unavailable", "message": "The assistant is not configured"},
        )
    return _claude_intake_assistant()


@lru_cache
def _claude_search_agent() -> ClaudeSearchAgent:
    return ClaudeSearchAgent(get_settings())


def get_search_agent(settings: Settings = Depends(get_settings)) -> SearchAgent:
    if not settings.anthropic_api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "ai_unavailable", "message": "The assistant is not configured"},
        )
    return _claude_search_agent()


@lru_cache
def _http_npi_client() -> HttpNpiClient:
    return HttpNpiClient()


def get_npi_client() -> NpiClient:
    return _http_npi_client()
