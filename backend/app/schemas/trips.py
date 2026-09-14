"""Schemas for /trips. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LeadSource, TripStatus, TripType


class TripBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    trip_number: str
    trip_type: TripType = TripType.CHARTER
    status: TripStatus = TripStatus.DRAFT
    account_holder_id: Optional[uuid.UUID] = None
    primary_contact_id: Optional[uuid.UUID] = None
    lead_passenger_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    ops_user_id: Optional[uuid.UUID] = None
    accepted_quote_id: Optional[uuid.UUID] = None
    booking_id: Optional[uuid.UUID] = None
    source_empty_leg_id: Optional[uuid.UUID] = None
    source: LeadSource = LeadSource.OTHER
    pax_count: int = 0
    leg_count: int = 0
    departure_date: Optional[date] = None
    return_date: Optional[date] = None
    currency: str = 'USD'
    total_sell_cents: int = 0
    total_cost_cents: int = 0
    special_requests: Optional[str] = None
    internal_notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None


class TripCreate(TripBase):
    pass


class TripUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    trip_number: Optional[str] = None
    trip_type: Optional[TripType] = None
    status: Optional[TripStatus] = None
    account_holder_id: Optional[uuid.UUID] = None
    primary_contact_id: Optional[uuid.UUID] = None
    lead_passenger_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    ops_user_id: Optional[uuid.UUID] = None
    accepted_quote_id: Optional[uuid.UUID] = None
    booking_id: Optional[uuid.UUID] = None
    source_empty_leg_id: Optional[uuid.UUID] = None
    source: Optional[LeadSource] = None
    pax_count: Optional[int] = None
    leg_count: Optional[int] = None
    departure_date: Optional[date] = None
    return_date: Optional[date] = None
    currency: Optional[str] = None
    total_sell_cents: Optional[int] = None
    total_cost_cents: Optional[int] = None
    special_requests: Optional[str] = None
    internal_notes: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None


class TripRead(TripBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    margin_cents: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class TripList(BaseModel):
    items: list[TripRead]
    total: int
    page: int
    page_size: int
