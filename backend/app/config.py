"""Application settings. Read from the environment (and backend/.env), APP_ prefix.

    APP_DATABASE_URL          runtime connection -- MUST be the bitlux_app role (DATA_MODEL 1.7)
    APP_JWT_SECRET            HS256 key for access tokens      (also accepted: JWT_SECRET)
    APP_JWT_REFRESH_SECRET    HS256 key for refresh tokens     (also accepted: JWT_REFRESH_SECRET)
    APP_FIELD_ENCRYPTION_KEY  Fernet key for [enc] columns
    APP_CORS_ORIGINS          comma-separated list
    APP_ENV                   local | test | staging | production

The insecure defaults exist so `make up migrate seed` works with no setup. In
any environment other than local/test, missing secrets are a startup error.
"""

from __future__ import annotations

import base64
import hashlib
from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# 48 chars so HS256 does not warn about key length even on the dev default.
_DEV_ONLY = "dev-only-not-a-secret-do-not-deploy-this-value-0"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="APP_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    env: str = "local"
    log_level: str = "INFO"
    api_title: str = "Bitlux CRM API"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://bitlux_app:bitlux_app@localhost:5433/bitlux_crm"
    db_pool_size: int = 5
    db_echo: bool = False

    jwt_secret: str = Field(default=_DEV_ONLY, validation_alias=AliasChoices("APP_JWT_SECRET", "JWT_SECRET"))
    jwt_refresh_secret: str = Field(default=_DEV_ONLY + "-refresh", validation_alias=AliasChoices("APP_JWT_REFRESH_SECRET", "JWT_REFRESH_SECRET"))
    jwt_algorithm: str = "HS256"
    jwt_issuer: str = "bitlux-crm"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7

    field_encryption_key: str = Field(default=_DEV_ONLY + "-fields", validation_alias=AliasChoices("APP_FIELD_ENCRYPTION_KEY", "FIELD_ENCRYPTION_KEY"))

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    graph_max_nodes: int = 200
    search_default_limit: int = 5
    search_max_limit: int = 25

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @property
    def is_local(self) -> bool:
        return self.env in ("local", "test")

    @property
    def fernet_key(self) -> bytes:
        """Fernet needs 32 url-safe base64 bytes; derive from whatever string was given."""
        return base64.urlsafe_b64encode(hashlib.sha256(self.field_encryption_key.encode()).digest())

    def assert_production_safe(self) -> None:
        if self.is_local:
            return
        weak = [n for n in ("jwt_secret", "jwt_refresh_secret", "field_encryption_key") if getattr(self, n).startswith(_DEV_ONLY)]
        if weak:
            raise RuntimeError(f"APP_ENV={self.env!r} but these are still dev defaults: {', '.join(weak)}")


@lru_cache
def get_settings() -> Settings:
    return Settings()
