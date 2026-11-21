from collections.abc import Callable
from functools import lru_cache

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.phone import normalize_phone
from app.core.security import AuthError, AuthUser, decode_supabase_token
from app.db.session import get_db
from app.models import Profile
from app.models.enums import UserRole
from app.services.ai_intake import ClaudeIntakeAssistant, IntakeAssistant
from app.services.ai_listing import ClaudeListingDrafter, ListingDrafter
from app.services.ai_menu import ClaudeMenuReader, MenuReader
from app.services.ai_search import ClaudeSearchAgent, SearchAgent
from app.services.npi import HttpNpiClient, NpiClient
from app.services.osm import HttpOsmClient, OsmClient
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


def _clean(value: object, limit: int) -> str | None:
    return str(value).strip()[:limit] or None if value else None


def _registration(meta: dict) -> dict[str, str | bool | None]:
    """Profile fields from the sign-up form (Supabase `user_metadata`) or Google."""
    first, last = _clean(meta.get("first_name"), 60), _clean(meta.get("last_name"), 60)
    full = " ".join(x for x in (first, last) if x) or meta.get("full_name") or meta.get("name")
    return {
        "first_name": first,
        "last_name": last,
        "display_name": _clean(full, 80),
        "phone": normalize_phone(meta.get("phone")),
        "whatsapp": (whatsapp := normalize_phone(meta.get("whatsapp"))),
        "whatsapp_opt_in": whatsapp is not None,
    }


def get_current_profile(
    user: AuthUser = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Profile:
    """Return the caller's profile, creating it on first sight (just-in-time provisioning)."""
    meta = user.claims.get("user_metadata") or {}
    profile = db.get(Profile, user.id)
    if profile is None:
        stmt = (
            insert(Profile)
            .values(
                id=user.id,
                email=user.email,
                avatar_url=meta.get("avatar_url"),
                **_registration(meta),
            )
            .on_conflict_do_nothing(index_elements=[Profile.id])
        )
        db.execute(stmt)
        db.commit()
        profile = db.get(Profile, user.id)
        assert profile is not None
    elif profile.first_name is None and meta.get("first_name"):
        # Signed in before registering with a name (e.g. an older email-link account).
        for key, value in _registration(meta).items():
            if value and not getattr(profile, key):
                setattr(profile, key, value)
        db.commit()
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


@lru_cache
def _http_osm_client() -> HttpOsmClient:
    return HttpOsmClient()


def get_osm_client() -> OsmClient:
    return _http_osm_client()
