"""Schemas for /invoices. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import InvoiceStatus, InvoiceType, LineItemType, PaymentTerms


class InvoiceBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    invoice_number: str
    invoice_type: InvoiceType = InvoiceType.FULL
    status: InvoiceStatus = InvoiceStatus.DRAFT
    account_holder_id: uuid.UUID
    booking_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None
    parent_invoice_id: Optional[uuid.UUID] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: PaymentTerms = PaymentTerms.DUE_ON_RECEIPT
    currency: str = 'USD'
    exchange_rate: float = 1
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    amount_paid_cents: int = 0
    billing_address_id: Optional[uuid.UUID] = None
    pdf_document_id: Optional[uuid.UUID] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    external_ref: Optional[str] = None
    notes: Optional[str] = None


class InvoiceCreate(InvoiceBase):
    pass


class InvoiceUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    invoice_number: Optional[str] = None
    invoice_type: Optional[InvoiceType] = None
    status: Optional[InvoiceStatus] = None
    account_holder_id: Optional[uuid.UUID] = None
    booking_id: Optional[uuid.UUID] = None
    trip_id: Optional[uuid.UUID] = None
    parent_invoice_id: Optional[uuid.UUID] = None
    issue_date: Optional[date] = None
    due_date: Optional[date] = None
    payment_terms: Optional[PaymentTerms] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    subtotal_cents: Optional[int] = None
    tax_cents: Optional[int] = None
    total_cents: Optional[int] = None
    amount_paid_cents: Optional[int] = None
    billing_address_id: Optional[uuid.UUID] = None
    pdf_document_id: Optional[uuid.UUID] = None
    sent_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    voided_at: Optional[datetime] = None
    void_reason: Optional[str] = None
    external_ref: Optional[str] = None
    notes: Optional[str] = None


class InvoiceRead(InvoiceBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    balance_cents: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class InvoiceList(BaseModel):
    items: list[InvoiceRead]
    total: int
    page: int
    page_size: int


class InvoiceLineItemBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    invoice_id: uuid.UUID
    quote_line_item_id: Optional[uuid.UUID] = None
    leg_id: Optional[uuid.UUID] = None
    line_type: LineItemType
    description: str
    quantity: float = 1
    unit: Optional[str] = None
    unit_price_cents: int = 0
    amount_cents: int = 0
    is_taxable: bool = True
    tax_rate: float = 0
    tax_cents: int = 0
    gl_account_code: Optional[str] = None
    sort_order: int = 0


class InvoiceLineItemCreate(InvoiceLineItemBase):
    pass


class InvoiceLineItemUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    invoice_id: Optional[uuid.UUID] = None
    quote_line_item_id: Optional[uuid.UUID] = None
    leg_id: Optional[uuid.UUID] = None
    line_type: Optional[LineItemType] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price_cents: Optional[int] = None
    amount_cents: Optional[int] = None
    is_taxable: Optional[bool] = None
    tax_rate: Optional[float] = None
    tax_cents: Optional[int] = None
    gl_account_code: Optional[str] = None
    sort_order: Optional[int] = None


class InvoiceLineItemRead(InvoiceLineItemBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class InvoiceLineItemList(BaseModel):
    items: list[InvoiceLineItemRead]
    total: int
    page: int
    page_size: int
