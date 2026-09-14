"""Schemas for /bookings. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import BookingStatus


class BookingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    booking_number: str
    trip_id: uuid.UUID
    quote_id: uuid.UUID
    account_holder_id: uuid.UUID
    status: BookingStatus = BookingStatus.PENDING
    operator_id: Optional[uuid.UUID] = None
    operator_confirmation_ref: Optional[str] = None
    contract_document_id: Optional[uuid.UUID] = None
    signed_by_contact_id: Optional[uuid.UUID] = None
    esign_envelope_id: Optional[str] = None
    currency: str = 'USD'
    total_cents: int = 0
    cost_cents: int = 0
    deposit_required_cents: int = 0
    deposit_due_at: Optional[datetime] = None
    deposit_received_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    contract_sent_at: Optional[datetime] = None
    contract_signed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cancellation_fee_cents: int = 0


class BookingCreate(BookingBase):
    pass


class BookingUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    booking_number: Optional[str] = None
    trip_id: Optional[uuid.UUID] = None
    quote_id: Optional[uuid.UUID] = None
    account_holder_id: Optional[uuid.UUID] = None
    status: Optional[BookingStatus] = None
    operator_id: Optional[uuid.UUID] = None
    operator_confirmation_ref: Optional[str] = None
    contract_document_id: Optional[uuid.UUID] = None
    signed_by_contact_id: Optional[uuid.UUID] = None
    esign_envelope_id: Optional[str] = None
    currency: Optional[str] = None
    total_cents: Optional[int] = None
    cost_cents: Optional[int] = None
    deposit_required_cents: Optional[int] = None
    deposit_due_at: Optional[datetime] = None
    deposit_received_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    contract_sent_at: Optional[datetime] = None
    contract_signed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    cancellation_policy: Optional[str] = None
    cancellation_fee_cents: Optional[int] = None


class BookingRead(BookingBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    margin_cents: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class BookingList(BaseModel):
    items: list[BookingRead]
    total: int
    page: int
    page_size: int
