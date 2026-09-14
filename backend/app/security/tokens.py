"""JWT access and refresh tokens (HS256).

Access tokens are stateless and short-lived (15 min). Refresh tokens are long-
lived (7 days) and *stateful*: a SHA-256 of each one is stored in
``refresh_tokens`` so it can be rotated on use and revoked on logout.
"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt

from app.config import get_settings

TokenType = Literal["access", "refresh"]


class TokenError(Exception):
    """Invalid, expired, or wrong-type token."""


@dataclass(frozen=True)
class Claims:
    user_id: uuid.UUID
    client_id: uuid.UUID
    role: str
    token_type: TokenType
    jti: uuid.UUID
    expires_at: datetime


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _secret(token_type: TokenType) -> str:
    s = get_settings()
    return s.jwt_secret if token_type == "access" else s.jwt_refresh_secret


def issue(user_id: uuid.UUID, client_id: uuid.UUID, role: str, token_type: TokenType, jti: uuid.UUID | None = None) -> tuple[str, Claims]:
    s = get_settings()
    ttl = timedelta(minutes=s.access_token_ttl_minutes) if token_type == "access" else timedelta(days=s.refresh_token_ttl_days)
    now = _now()
    claims = Claims(user_id, client_id, role, token_type, jti or uuid.uuid4(), now + ttl)
    payload = {
        "sub": str(user_id), "cid": str(client_id), "role": role, "typ": token_type,
        "jti": str(claims.jti), "iat": int(now.timestamp()), "exp": int(claims.expires_at.timestamp()),
        "iss": s.jwt_issuer,
    }
    return jwt.encode(payload, _secret(token_type), algorithm=s.jwt_algorithm), claims


def decode(token: str, expected: TokenType) -> Claims:
    s = get_settings()
    try:
        payload = jwt.decode(token, _secret(expected), algorithms=[s.jwt_algorithm], issuer=s.jwt_issuer,
                             options={"require": ["sub", "cid", "typ", "jti", "exp"]})
    except jwt.ExpiredSignatureError as e:
        raise TokenError("token has expired") from e
    except jwt.InvalidTokenError as e:
        raise TokenError("invalid token") from e
    if payload.get("typ") != expected:
        raise TokenError(f"expected a {expected} token")
    return Claims(
        user_id=uuid.UUID(payload["sub"]), client_id=uuid.UUID(payload["cid"]), role=payload.get("role", ""),
        token_type=expected, jti=uuid.UUID(payload["jti"]), expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
    )


def fingerprint(token: str) -> str:
    """What gets stored for a refresh token: its SHA-256, never the token."""
    return hashlib.sha256(token.encode()).hexdigest()
