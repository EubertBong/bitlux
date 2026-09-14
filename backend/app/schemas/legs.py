"""Schemas for /legs. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CrewRole, LegPurpose, LegStatus


class LegBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    trip_id: uuid.UUID
    leg_number: int
    status: LegStatus = LegStatus.SCHEDULED
    purpose: LegPurpose = LegPurpose.REVENUE
    departure_airport_id: uuid.UUID
    arrival_airport_id: uuid.UUID
    departure_fbo_id: Optional[uuid.UUID] = None
    arrival_fbo_id: Optional[uuid.UUID] = None
    scheduled_departure_at: datetime
    scheduled_arrival_at: datetime
    departure_timezone: str
    arrival_timezone: str
    actual_departure_at: Optional[datetime] = None
    actual_arrival_at: Optional[datetime] = None
    block_time_minutes: Optional[int] = None
    flight_time_minutes: Optional[int] = None
    distance_nm: Optional[int] = None
    aircraft_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    flight_number: Optional[str] = None
    pax_count: int = 0
    baggage_notes: Optional[str] = None
    catering_notes: Optional[str] = None
    ground_transport: dict[str, Any] = Field(default_factory=dict)
    customs_required: bool = False
    is_tech_stop: bool = False
    cost_cents: int = 0
    sell_cents: int = 0
    delay_minutes: Optional[int] = None
    delay_reason: Optional[str] = None


class LegCreate(LegBase):
    pass


class LegUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    trip_id: Optional[uuid.UUID] = None
    leg_number: Optional[int] = None
    status: Optional[LegStatus] = None
    purpose: Optional[LegPurpose] = None
    departure_airport_id: Optional[uuid.UUID] = None
    arrival_airport_id: Optional[uuid.UUID] = None
    departure_fbo_id: Optional[uuid.UUID] = None
    arrival_fbo_id: Optional[uuid.UUID] = None
    scheduled_departure_at: Optional[datetime] = None
    scheduled_arrival_at: Optional[datetime] = None
    departure_timezone: Optional[str] = None
    arrival_timezone: Optional[str] = None
    actual_departure_at: Optional[datetime] = None
    actual_arrival_at: Optional[datetime] = None
    block_time_minutes: Optional[int] = None
    flight_time_minutes: Optional[int] = None
    distance_nm: Optional[int] = None
    aircraft_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    flight_number: Optional[str] = None
    pax_count: Optional[int] = None
    baggage_notes: Optional[str] = None
    catering_notes: Optional[str] = None
    ground_transport: Optional[dict[str, Any]] = None
    customs_required: Optional[bool] = None
    is_tech_stop: Optional[bool] = None
    cost_cents: Optional[int] = None
    sell_cents: Optional[int] = None
    delay_minutes: Optional[int] = None
    delay_reason: Optional[str] = None


class LegRead(LegBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class LegList(BaseModel):
    items: list[LegRead]
    total: int
    page: int
    page_size: int


class LegPassengerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    leg_id: uuid.UUID
    passenger_id: uuid.UUID
    is_lead_passenger: bool = False
    seat_assignment: Optional[str] = None
    travel_document_id: Optional[uuid.UUID] = None
    catering_selection: dict[str, Any] = Field(default_factory=dict)
    special_requests: Optional[str] = None
    checked_in_at: Optional[datetime] = None
    boarded_at: Optional[datetime] = None
    is_no_show: bool = False
    manifest_submitted_at: Optional[datetime] = None


class LegPassengerCreate(LegPassengerBase):
    pass


class LegPassengerUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    leg_id: Optional[uuid.UUID] = None
    passenger_id: Optional[uuid.UUID] = None
    is_lead_passenger: Optional[bool] = None
    seat_assignment: Optional[str] = None
    travel_document_id: Optional[uuid.UUID] = None
    catering_selection: Optional[dict[str, Any]] = None
    special_requests: Optional[str] = None
    checked_in_at: Optional[datetime] = None
    boarded_at: Optional[datetime] = None
    is_no_show: Optional[bool] = None
    manifest_submitted_at: Optional[datetime] = None


class LegPassengerRead(LegPassengerBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class LegPassengerList(BaseModel):
    items: list[LegPassengerRead]
    total: int
    page: int
    page_size: int


class LegCrewBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    leg_id: uuid.UUID
    crew_member_id: uuid.UUID
    crew_role: CrewRole
    duty_start_at: Optional[datetime] = None
    duty_end_at: Optional[datetime] = None
    hotel_details: dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = None


class LegCrewCreate(LegCrewBase):
    pass


class LegCrewUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    leg_id: Optional[uuid.UUID] = None
    crew_member_id: Optional[uuid.UUID] = None
    crew_role: Optional[CrewRole] = None
    duty_start_at: Optional[datetime] = None
    duty_end_at: Optional[datetime] = None
    hotel_details: Optional[dict[str, Any]] = None
    notes: Optional[str] = None


class LegCrewRead(LegCrewBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class LegCrewList(BaseModel):
    items: list[LegCrewRead]
    total: int
    page: int
    page_size: int
