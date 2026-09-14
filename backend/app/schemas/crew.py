"""Schemas for /crew. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import CrewRole, CrewStatus


class CrewMemberBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    operator_id: Optional[uuid.UUID] = None
    first_name: str
    last_name: str
    primary_role: CrewRole = CrewRole.PIC
    status: CrewStatus = CrewStatus.ACTIVE
    date_of_birth: Optional[date] = None
    nationality_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    license_type: Optional[str] = None
    license_country: Optional[str] = None
    medical_class: Optional[str] = None
    medical_expiry: Optional[date] = None
    type_ratings: list[str] = Field(default_factory=list)
    total_hours: Optional[int] = None
    hours_on_type: dict[str, Any] = Field(default_factory=dict)
    base_airport_id: Optional[uuid.UUID] = None
    photo_document_id: Optional[uuid.UUID] = None
    last_recurrent_at: Optional[date] = None
    next_recurrent_due: Optional[date] = None
    notes: Optional[str] = None


class CrewMemberCreate(CrewMemberBase):
    license_number: Optional[str] = Field(default=None, description="Plaintext; stored encrypted, returned only as *_last4.")


class CrewMemberUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    operator_id: Optional[uuid.UUID] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    primary_role: Optional[CrewRole] = None
    status: Optional[CrewStatus] = None
    date_of_birth: Optional[date] = None
    nationality_code: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    license_type: Optional[str] = None
    license_country: Optional[str] = None
    medical_class: Optional[str] = None
    medical_expiry: Optional[date] = None
    type_ratings: Optional[list[str]] = None
    total_hours: Optional[int] = None
    hours_on_type: Optional[dict[str, Any]] = None
    base_airport_id: Optional[uuid.UUID] = None
    photo_document_id: Optional[uuid.UUID] = None
    last_recurrent_at: Optional[date] = None
    next_recurrent_due: Optional[date] = None
    notes: Optional[str] = None
    license_number: Optional[str] = None


class CrewMemberRead(CrewMemberBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    license_last4: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class CrewMemberList(BaseModel):
    items: list[CrewMemberRead]
    total: int
    page: int
    page_size: int
