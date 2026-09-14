"""Auth request/response shapes."""

from __future__ import annotations

import uuid
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import EmailAddress
from app.models.enums import UserRole, UserStatus


class LoginRequest(BaseModel):
    email: EmailAddress
    password: str = Field(min_length=1)
    client_slug: Optional[str] = Field(default=None, description="Required only if the email exists in more than one tenant.")


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class RefreshRequest(BaseModel):
    """The token may come in the body (API clients) or in the HttpOnly cookie (the SPA)."""
    refresh_token: Optional[str] = None


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class MeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    client_id: uuid.UUID
    email: str
    full_name: str
    role: UserRole
    status: UserStatus
    timezone: Optional[str] = None
    permissions: list[str]
