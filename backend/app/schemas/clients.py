"""Schemas for /clients. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ClientStatus


class ClientBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    slug: str
    name: str
    legal_name: Optional[str] = None
    status: ClientStatus = ClientStatus.TRIALING
    default_currency: str = 'USD'
    timezone: str = 'UTC'
    locale: str = 'en-US'
    billing_email: Optional[str] = None
    support_email: Optional[str] = None
    logo_url: Optional[str] = None
    settings: dict[str, Any] = Field(default_factory=dict)
    feature_flags: dict[str, Any] = Field(default_factory=dict)
    trip_number_prefix: Optional[str] = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    slug: Optional[str] = None
    name: Optional[str] = None
    legal_name: Optional[str] = None
    status: Optional[ClientStatus] = None
    default_currency: Optional[str] = None
    timezone: Optional[str] = None
    locale: Optional[str] = None
    billing_email: Optional[str] = None
    support_email: Optional[str] = None
    logo_url: Optional[str] = None
    settings: Optional[dict[str, Any]] = None
    feature_flags: Optional[dict[str, Any]] = None
    trip_number_prefix: Optional[str] = None


class ClientRead(ClientBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class ClientList(BaseModel):
    items: list[ClientRead]
    total: int
    page: int
    page_size: int
