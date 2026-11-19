from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://cc:cc_dev_password@localhost:5432/community_connect"

    # Comma-separated list, e.g. "http://localhost:3000,https://communityconnect.app"
    cors_origins: str = "http://localhost:3000"

    # Supabase Auth. Tokens signed with asymmetric keys are verified via JWKS
    # ({supabase_url}/auth/v1/.well-known/jwks.json); legacy HS256 tokens need the secret.
    supabase_url: str = ""
    supabase_jwt_secret: str = ""
    supabase_jwt_audience: str = "authenticated"

    # Default map centre: Fairfax, VA (Northern Virginia)
    default_lat: float = 38.8462
    default_lng: float = -77.3064
    default_radius_km: float = 40.0

    # Supabase Storage (listing photos). The service-role key is server-only: it bypasses RLS,
    # so it must never reach the browser. Photos are stored in a private bucket and served
    # through short-lived signed URLs.
    supabase_service_role_key: str = ""
    storage_bucket: str = "listing-photos"
    signed_url_ttl_seconds: int = 3600

    # Photo uploads
    max_photos_per_listing: int = 5
    max_upload_mb: int = 12
    image_max_dimension: int = 2048

    # Claude (AI listing drafts)
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"
    claude_timeout_seconds: float = 90.0
    # Per-user limits on AI draft requests (successful or not), to cap cost and abuse.
    ai_drafts_per_hour: int = 10
    ai_drafts_per_day: int = 30
    # Chat turns with the "add your business" assistant (each message is one AI call).
    ai_chat_turns_per_hour: int = 60
    ai_chat_turns_per_day: int = 200

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_issuer(self) -> str | None:
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else None

    @property
    def storage_configured(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
