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

    # Phase 2+
    anthropic_api_key: str = ""
    claude_model: str = "claude-opus-5-5"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def supabase_issuer(self) -> str | None:
        return f"{self.supabase_url.rstrip('/')}/auth/v1" if self.supabase_url else None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
