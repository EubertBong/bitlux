"""Schemas for /passengers. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PassengerStatus, TravelDocumentType


class PassengerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    contact_id: Optional[uuid.UUID] = None
    status: PassengerStatus = PassengerStatus.ACTIVE
    first_name: str
    middle_name: Optional[str] = None
    last_name: str
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_code: Optional[str] = None
    gender_marker: Optional[str] = None
    weight_kg: Optional[float] = None
    guardian_passenger_id: Optional[uuid.UUID] = None
    dietary_restrictions: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    mobility_assistance: bool = False
    travels_with_pet: bool = False
    pet_details: Optional[dict[str, Any]] = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None


class PassengerCreate(PassengerBase):
    known_traveler_number: Optional[str] = Field(default=None, description="Plaintext; stored encrypted, returned only as *_last4.")
    redress_number: Optional[str] = Field(default=None, description="Plaintext; stored encrypted, returned only as *_last4.")


class PassengerUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contact_id: Optional[uuid.UUID] = None
    status: Optional[PassengerStatus] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    preferred_name: Optional[str] = None
    suffix: Optional[str] = None
    date_of_birth: Optional[date] = None
    nationality_code: Optional[str] = None
    gender_marker: Optional[str] = None
    weight_kg: Optional[float] = None
    guardian_passenger_id: Optional[uuid.UUID] = None
    dietary_restrictions: Optional[list[str]] = None
    allergies: Optional[list[str]] = None
    mobility_assistance: Optional[bool] = None
    travels_with_pet: Optional[bool] = None
    pet_details: Optional[dict[str, Any]] = None
    preferences: Optional[dict[str, Any]] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    notes: Optional[str] = None
    known_traveler_number: Optional[str] = None
    redress_number: Optional[str] = None


class PassengerRead(PassengerBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    ktn_last4: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class PassengerList(BaseModel):
    items: list[PassengerRead]
    total: int
    page: int
    page_size: int


class TravelDocumentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    passenger_id: Optional[uuid.UUID] = None
    crew_member_id: Optional[uuid.UUID] = None
    document_type: TravelDocumentType
    full_name_on_document: str
    issuing_country: str
    nationality_code: Optional[str] = None
    place_of_birth: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    scan_document_id: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[uuid.UUID] = None
    is_primary: bool = False


class TravelDocumentCreate(TravelDocumentBase):
    number: str = Field(min_length=1, description="Plaintext; stored encrypted, returned only as number_last4.")


class TravelDocumentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    passenger_id: Optional[uuid.UUID] = None
    crew_member_id: Optional[uuid.UUID] = None
    document_type: Optional[TravelDocumentType] = None
    full_name_on_document: Optional[str] = None
    issuing_country: Optional[str] = None
    nationality_code: Optional[str] = None
    place_of_birth: Optional[str] = None
    issue_date: Optional[date] = None
    expiry_date: Optional[date] = None
    scan_document_id: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[uuid.UUID] = None
    is_primary: Optional[bool] = None
    number: Optional[str] = None


class TravelDocumentRead(TravelDocumentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    number_last4: str
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class TravelDocumentList(BaseModel):
    items: list[TravelDocumentRead]
    total: int
    page: int
    page_size: int
