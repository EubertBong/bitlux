"""Application settings. Read from the environment (and backend/.env), APP_ prefix.

    APP_DATABASE_URL          runtime connection -- MUST be the bitlux_app role (DATA_MODEL 1.7).
                              Deliberately NOT plain DATABASE_URL: that name is the schema
                              owner used by alembic / scripts, and running the API as the
                              owner would silently disable row-level security.
    APP_JWT_SECRET            HS256 key for access tokens      (also accepted: JWT_SECRET)
    APP_JWT_REFRESH_SECRET    HS256 key for refresh tokens     (also accepted: JWT_REFRESH_SECRET)
    APP_FIELD_ENCRYPTION_KEY  Fernet key for [enc] columns     (also accepted: FIELD_ENCRYPTION_KEY)
    APP_CORS_ORIGINS          JSON list or comma-separated     (also accepted: CORS_ORIGINS)
    APP_REFRESH_COOKIE_SAMESITE / _SECURE                      (also accepted without APP_)
    APP_ENV                   local | test | staging | production

The insecure defaults exist so `make up migrate seed` works with no setup. In
any environment other than local/test, missing secrets are a startup error.
"""

from __future__ import annotations

import base64
import hashlib
import json
from functools import lru_cache
from typing import Annotated, Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

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

    # NoDecode: pydantic-settings would otherwise insist the env value is JSON and
    # reject the comma-separated form; the validator below accepts both.
    cors_origins: Annotated[list[str], NoDecode] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        validation_alias=AliasChoices("APP_CORS_ORIGINS", "CORS_ORIGINS"),
    )

    # Refresh token cookie (HttpOnly). The SPA keeps the access token in memory
    # only and relies on this cookie to obtain a new one; it never sees or stores
    # the refresh token. secure=None means "secure unless APP_ENV is local/test".
    refresh_cookie_name: str = "bitlux_refresh"
    refresh_cookie_secure: bool | None = Field(default=None, validation_alias=AliasChoices("APP_REFRESH_COOKIE_SECURE", "REFRESH_COOKIE_SECURE"))
    # 'none' (+ secure) when the SPA is on another site, e.g. Cloudflare Pages -> Render.
    refresh_cookie_samesite: str = Field(default="lax", validation_alias=AliasChoices("APP_REFRESH_COOKIE_SAMESITE", "REFRESH_COOKIE_SAMESITE"))
    graph_max_nodes: int = 200
    search_default_limit: int = 5
    search_max_limit: int = 25

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_origins(cls, v: object) -> object:
        """Accept a JSON list ('["https://a"]') or a comma-separated string; strip trailing slashes."""
        if isinstance(v, str):
            text = v.strip()
            v = json.loads(text) if text.startswith("[") else [x.strip() for x in text.split(",") if x.strip()]
        if isinstance(v, (list, tuple)):
            return [str(o).strip().rstrip("/") for o in v if str(o).strip()]
        return v

    @field_validator("refresh_cookie_samesite")
    @classmethod
    def _samesite(cls, v: str) -> str:
        v = v.lower()
        if v not in ("lax", "strict", "none"):
            raise ValueError("refresh_cookie_samesite must be lax, strict or none")
        return v

    @property
    def is_local(self) -> bool:
        return self.env in ("local", "test")

    @property
    def refresh_cookie_is_secure(self) -> bool:
        return (not self.is_local) if self.refresh_cookie_secure is None else self.refresh_cookie_secure

    @property
    def refresh_cookie_path(self) -> str:
        return f"{self.api_prefix}/auth"  # only ever sent to the auth endpoints

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
        if self.database_url == type(self).model_fields["database_url"].default:
            raise RuntimeError(f"APP_ENV={self.env!r} but APP_DATABASE_URL is not set (the runtime must connect as the bitlux_app role)")
        if self.refresh_cookie_samesite == "none" and not self.refresh_cookie_is_secure:
            raise RuntimeError("REFRESH_COOKIE_SAMESITE=none requires REFRESH_COOKIE_SECURE=true (browsers drop the cookie otherwise)")


_SSLMODE_TO_ASYNCPG = {"disable": False, "allow": "prefer", "prefer": "prefer", "require": "require",
                       "verify-ca": "verify-ca", "verify-full": "verify-full"}


def asyncpg_engine_args(url: str) -> tuple[str, dict[str, Any]]:
    """Normalise a libpq-style URL (what Neon, Render and psql hand out) for SQLAlchemy + asyncpg.

    * ``postgres://`` / ``postgresql://`` become ``postgresql+asyncpg://``.
    * ``?sslmode=`` and ``?channel_binding=`` are libpq-only. SQLAlchemy forwards unknown
      query parameters to ``asyncpg.connect()`` verbatim, which rejects them, so they are
      removed here and ``sslmode`` is translated into asyncpg's ``ssl=`` connect argument.
    Returns ``(url, connect_args)`` for ``create_async_engine``.
    """
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
    parts = urlsplit(url)
    query = parse_qsl(parts.query, keep_blank_values=True)
    connect_args: dict[str, Any] = {}
    kept = []
    for k, v in query:
        if k == "sslmode":
            ssl = _SSLMODE_TO_ASYNCPG.get(v.lower())
            if ssl is None:
                raise ValueError(f"unknown sslmode {v!r} in database URL")
            connect_args["ssl"] = ssl
        elif k == "channel_binding":
            continue
        else:
            kept.append((k, v))
    return urlunsplit(parts._replace(query=urlencode(kept))), connect_args


@lru_cache
def get_settings() -> Settings:
    return Settings()
