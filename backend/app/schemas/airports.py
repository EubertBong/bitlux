"""Schemas for /airports. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AirportBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    icao_code: Optional[str] = None
    iata_code: Optional[str] = None
    local_code: Optional[str] = None
    name: str
    city: Optional[str] = None
    region: Optional[str] = None
    country_code: str
    latitude: float
    longitude: float
    elevation_ft: Optional[int] = None
    timezone: str
    longest_runway_ft: Optional[int] = None
    has_customs: bool = False
    is_towered: Optional[bool] = None
    is_private: bool = False
    slot_restricted: bool = False
    curfew: Optional[dict[str, Any]] = None
    is_active: bool = True


class AirportCreate(AirportBase):
    pass


class AirportUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    icao_code: Optional[str] = None
    iata_code: Optional[str] = None
    local_code: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    country_code: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    elevation_ft: Optional[int] = None
    timezone: Optional[str] = None
    longest_runway_ft: Optional[int] = None
    has_customs: Optional[bool] = None
    is_towered: Optional[bool] = None
    is_private: Optional[bool] = None
    slot_restricted: Optional[bool] = None
    curfew: Optional[dict[str, Any]] = None
    is_active: Optional[bool] = None


class AirportRead(AirportBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AirportList(BaseModel):
    items: list[AirportRead]
    total: int
    page: int
    page_size: int


class FBOBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    airport_id: uuid.UUID
    name: str
    brand: Optional[str] = None
    phone: Optional[str] = None
    unicom_frequency: Optional[str] = None
    address_line: Optional[str] = None
    fuel_brand: Optional[str] = None
    has_customs: bool = False
    hours_of_operation: Optional[str] = None
    is_preferred: bool = False
    notes: Optional[str] = None


class FBOCreate(FBOBase):
    pass


class FBOUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    airport_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    phone: Optional[str] = None
    unicom_frequency: Optional[str] = None
    address_line: Optional[str] = None
    fuel_brand: Optional[str] = None
    has_customs: Optional[bool] = None
    hours_of_operation: Optional[str] = None
    is_preferred: Optional[bool] = None
    notes: Optional[str] = None


class FBORead(FBOBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class FBOList(BaseModel):
    items: list[FBORead]
    total: int
    page: int
    page_size: int
