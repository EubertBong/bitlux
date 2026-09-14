"""Schemas for /admin. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import ActorType, AuditAction, EntityType, UserRole, UserStatus
from app.security.crypto import redact


class UserBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    email: str
    full_name: str
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    role: UserRole = UserRole.BROKER
    status: UserStatus = UserStatus.INVITED
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    auth_provider: Optional[str] = None
    auth_subject: Optional[str] = None
    mfa_enabled: bool = False
    last_login_at: Optional[datetime] = None


class UserCreate(UserBase):
    password: str = Field(min_length=8, description="Set on create; stored as an argon2id hash, never returned.")


class UserUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    email: Optional[str] = None
    full_name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
    auth_provider: Optional[str] = None
    auth_subject: Optional[str] = None
    mfa_enabled: Optional[bool] = None
    last_login_at: Optional[datetime] = None
    password: Optional[str] = Field(default=None, min_length=8)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class UserList(BaseModel):
    items: list[UserRead]
    total: int
    page: int
    page_size: int


class AuditLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    occurred_at: datetime
    created_at: datetime
    action: AuditAction
    entity_type: EntityType
    entity_id: Optional[uuid.UUID] = None
    entity_label: Optional[str] = None
    actor_type: ActorType
    actor_user_id: Optional[uuid.UUID] = None
    actor_label: str
    impersonated_by_user_id: Optional[uuid.UUID] = None
    api_key_id: Optional[uuid.UUID] = None
    changed_fields: Optional[list[str]] = None
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    request_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None

    @field_validator("before", "after", mode="before")
    @classmethod
    def _redact(cls, v: object) -> object:
        """Never echo an [enc] value even if a caller logged one (DATA_MODEL 5)."""
        return redact(v) if isinstance(v, dict) else v


class AuditLogList(BaseModel):
    items: list[AuditLogRead]
    total: int
    page: int
    page_size: int
