"""Schemas for /aircraft. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AircraftStatus


class AircraftBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    tail_number: str
    serial_number: Optional[str] = None
    aircraft_model_id: uuid.UUID
    operator_id: Optional[uuid.UUID] = None
    owner_contact_id: Optional[uuid.UUID] = None
    status: AircraftStatus = AircraftStatus.ACTIVE
    year_of_manufacture: Optional[int] = None
    registration_country: Optional[str] = None
    home_base_airport_id: Optional[uuid.UUID] = None
    max_passengers: Optional[int] = None
    configured_seats: Optional[int] = None
    divans: Optional[int] = None
    berths: Optional[int] = None
    interior_refurb_year: Optional[int] = None
    exterior_refurb_year: Optional[int] = None
    wifi_provider: Optional[str] = None
    amenities: dict[str, Any] = Field(default_factory=dict)
    pets_allowed: Optional[bool] = None
    smoking_allowed: bool = False
    lavatory_type: Optional[str] = None
    cargo_capacity_cuft: Optional[int] = None
    hourly_rate_cents: Optional[int] = None
    is_available_for_charter: bool = True
    last_verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class AircraftCreate(AircraftBase):
    pass


class AircraftUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    tail_number: Optional[str] = None
    serial_number: Optional[str] = None
    aircraft_model_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    owner_contact_id: Optional[uuid.UUID] = None
    status: Optional[AircraftStatus] = None
    year_of_manufacture: Optional[int] = None
    registration_country: Optional[str] = None
    home_base_airport_id: Optional[uuid.UUID] = None
    max_passengers: Optional[int] = None
    configured_seats: Optional[int] = None
    divans: Optional[int] = None
    berths: Optional[int] = None
    interior_refurb_year: Optional[int] = None
    exterior_refurb_year: Optional[int] = None
    wifi_provider: Optional[str] = None
    amenities: Optional[dict[str, Any]] = None
    pets_allowed: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    lavatory_type: Optional[str] = None
    cargo_capacity_cuft: Optional[int] = None
    hourly_rate_cents: Optional[int] = None
    is_available_for_charter: Optional[bool] = None
    last_verified_at: Optional[datetime] = None
    notes: Optional[str] = None


class AircraftRead(AircraftBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AircraftList(BaseModel):
    items: list[AircraftRead]
    total: int
    page: int
    page_size: int


class AircraftOperatorAssignmentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    aircraft_id: uuid.UUID
    operator_id: uuid.UUID
    effective_from: date
    effective_to: Optional[date] = None
    is_current: bool = True
    management_agreement_document_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class AircraftOperatorAssignmentCreate(AircraftOperatorAssignmentBase):
    pass


class AircraftOperatorAssignmentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    aircraft_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None
    is_current: Optional[bool] = None
    management_agreement_document_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class AircraftOperatorAssignmentRead(AircraftOperatorAssignmentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AircraftOperatorAssignmentList(BaseModel):
    items: list[AircraftOperatorAssignmentRead]
    total: int
    page: int
    page_size: int
