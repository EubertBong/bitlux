"""Schemas for /payments. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PaymentMethod, PaymentStatus


class PaymentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    account_holder_id: uuid.UUID
    invoice_id: Optional[uuid.UUID] = None
    method: PaymentMethod
    status: PaymentStatus = PaymentStatus.PENDING
    amount_cents: int
    currency: str = 'USD'
    exchange_rate: float = 1
    fee_cents: int = 0
    received_at: datetime
    cleared_at: Optional[datetime] = None
    reference: Optional[str] = None
    processor: Optional[str] = None
    processor_txn_id: Optional[str] = None
    refund_of_payment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class PaymentCreate(PaymentBase):
    pass


class PaymentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    account_holder_id: Optional[uuid.UUID] = None
    invoice_id: Optional[uuid.UUID] = None
    method: Optional[PaymentMethod] = None
    status: Optional[PaymentStatus] = None
    amount_cents: Optional[int] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    fee_cents: Optional[int] = None
    received_at: Optional[datetime] = None
    cleared_at: Optional[datetime] = None
    reference: Optional[str] = None
    processor: Optional[str] = None
    processor_txn_id: Optional[str] = None
    refund_of_payment_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class PaymentRead(PaymentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class PaymentList(BaseModel):
    items: list[PaymentRead]
    total: int
    page: int
    page_size: int
