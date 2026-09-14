"""Schemas for /manufacturers. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ManufacturerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    name: str
    short_name: Optional[str] = None
    code: Optional[str] = None
    country_code: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None
    is_active: bool = True


class ManufacturerCreate(ManufacturerBase):
    pass


class ManufacturerUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    name: Optional[str] = None
    short_name: Optional[str] = None
    code: Optional[str] = None
    country_code: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    founded_year: Optional[int] = None
    is_active: Optional[bool] = None


class ManufacturerRead(ManufacturerBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class ManufacturerList(BaseModel):
    items: list[ManufacturerRead]
    total: int
    page: int
    page_size: int
