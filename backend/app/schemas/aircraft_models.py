"""Schemas for /aircraft_models. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AircraftCategory


class AircraftModelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    manufacturer_id: uuid.UUID
    name: str
    family: Optional[str] = None
    icao_type_code: Optional[str] = None
    category: AircraftCategory
    max_passengers: Optional[int] = None
    typical_passengers: Optional[int] = None
    range_nm: Optional[int] = None
    cruise_speed_kt: Optional[int] = None
    max_altitude_ft: Optional[int] = None
    baggage_capacity_cuft: Optional[int] = None
    cabin_length_in: Optional[float] = None
    cabin_width_in: Optional[float] = None
    cabin_height_in: Optional[float] = None
    has_lavatory: Optional[bool] = None
    has_enclosed_lavatory: Optional[bool] = None
    wifi_available: Optional[bool] = None
    cabin_crew_standard: bool = False
    hourly_rate_low_cents: Optional[int] = None
    hourly_rate_high_cents: Optional[int] = None
    production_start_year: Optional[int] = None
    production_end_year: Optional[int] = None
    image_url: Optional[str] = None


class AircraftModelCreate(AircraftModelBase):
    pass


class AircraftModelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    manufacturer_id: Optional[uuid.UUID] = None
    name: Optional[str] = None
    family: Optional[str] = None
    icao_type_code: Optional[str] = None
    category: Optional[AircraftCategory] = None
    max_passengers: Optional[int] = None
    typical_passengers: Optional[int] = None
    range_nm: Optional[int] = None
    cruise_speed_kt: Optional[int] = None
    max_altitude_ft: Optional[int] = None
    baggage_capacity_cuft: Optional[int] = None
    cabin_length_in: Optional[float] = None
    cabin_width_in: Optional[float] = None
    cabin_height_in: Optional[float] = None
    has_lavatory: Optional[bool] = None
    has_enclosed_lavatory: Optional[bool] = None
    wifi_available: Optional[bool] = None
    cabin_crew_standard: Optional[bool] = None
    hourly_rate_low_cents: Optional[int] = None
    hourly_rate_high_cents: Optional[int] = None
    production_start_year: Optional[int] = None
    production_end_year: Optional[int] = None
    image_url: Optional[str] = None


class AircraftModelRead(AircraftModelBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AircraftModelList(BaseModel):
    items: list[AircraftModelRead]
    total: int
    page: int
    page_size: int
