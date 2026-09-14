"""Schemas for /empty_legs. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EmptyLegSource, EmptyLegStatus


class EmptyLegBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    operator_id: uuid.UUID
    aircraft_id: Optional[uuid.UUID] = None
    aircraft_model_id: Optional[uuid.UUID] = None
    source_leg_id: Optional[uuid.UUID] = None
    status: EmptyLegStatus = EmptyLegStatus.DRAFT
    source: EmptyLegSource = EmptyLegSource.MANUAL
    departure_airport_id: uuid.UUID
    arrival_airport_id: uuid.UUID
    earliest_departure_at: datetime
    latest_departure_at: datetime
    seats_available: Optional[int] = None
    asking_price_cents: int
    floor_price_cents: Optional[int] = None
    currency: str = 'USD'
    is_flexible_routing: bool = False
    routing_radius_nm: Optional[int] = None
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    booked_trip_id: Optional[uuid.UUID] = None
    external_ref: Optional[str] = None
    notes: Optional[str] = None


class EmptyLegCreate(EmptyLegBase):
    pass


class EmptyLegUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    operator_id: Optional[uuid.UUID] = None
    aircraft_id: Optional[uuid.UUID] = None
    aircraft_model_id: Optional[uuid.UUID] = None
    source_leg_id: Optional[uuid.UUID] = None
    status: Optional[EmptyLegStatus] = None
    source: Optional[EmptyLegSource] = None
    departure_airport_id: Optional[uuid.UUID] = None
    arrival_airport_id: Optional[uuid.UUID] = None
    earliest_departure_at: Optional[datetime] = None
    latest_departure_at: Optional[datetime] = None
    seats_available: Optional[int] = None
    asking_price_cents: Optional[int] = None
    floor_price_cents: Optional[int] = None
    currency: Optional[str] = None
    is_flexible_routing: Optional[bool] = None
    routing_radius_nm: Optional[int] = None
    published_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    booked_trip_id: Optional[uuid.UUID] = None
    external_ref: Optional[str] = None
    notes: Optional[str] = None


class EmptyLegRead(EmptyLegBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class EmptyLegList(BaseModel):
    items: list[EmptyLegRead]
    total: int
    page: int
    page_size: int
