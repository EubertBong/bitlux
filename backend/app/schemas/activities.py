"""Schemas for /activities. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ActivityDirection, ActivityType, EntityType


class ActivityBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    activity_type: ActivityType
    direction: ActivityDirection = ActivityDirection.OUTBOUND
    subject: Optional[str] = None
    body: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    account_holder_id: Optional[uuid.UUID] = None
    entity_type: Optional[EntityType] = None
    entity_id: Optional[uuid.UUID] = None
    occurred_at: datetime
    duration_minutes: Optional[int] = None
    external_ref: Optional[str] = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata", serialization_alias="metadata")


class ActivityCreate(ActivityBase):
    pass


class ActivityUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    activity_type: Optional[ActivityType] = None
    direction: Optional[ActivityDirection] = None
    subject: Optional[str] = None
    body: Optional[str] = None
    user_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    account_holder_id: Optional[uuid.UUID] = None
    entity_type: Optional[EntityType] = None
    entity_id: Optional[uuid.UUID] = None
    occurred_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    external_ref: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, alias="metadata", serialization_alias="metadata")


class ActivityRead(ActivityBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class ActivityList(BaseModel):
    items: list[ActivityRead]
    total: int
    page: int
    page_size: int
