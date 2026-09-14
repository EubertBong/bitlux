"""Schemas for /segments. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import SegmentType


class SegmentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    name: str
    code: Optional[str] = None
    segment_type: SegmentType = SegmentType.OTHER
    description: Optional[str] = None
    parent_segment_id: Optional[uuid.UUID] = None
    path: Optional[str] = None
    color: Optional[str] = None
    is_auto: bool = False
    criteria: dict[str, Any] = Field(default_factory=dict)
    sort_order: int = 0


class SegmentCreate(SegmentBase):
    pass


class SegmentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: Optional[str] = None
    code: Optional[str] = None
    segment_type: Optional[SegmentType] = None
    description: Optional[str] = None
    parent_segment_id: Optional[uuid.UUID] = None
    path: Optional[str] = None
    color: Optional[str] = None
    is_auto: Optional[bool] = None
    criteria: Optional[dict[str, Any]] = None
    sort_order: Optional[int] = None


class SegmentRead(SegmentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class SegmentList(BaseModel):
    items: list[SegmentRead]
    total: int
    page: int
    page_size: int
