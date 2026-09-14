"""Schemas for /quotes. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import LineItemType, QuoteStatus


class QuoteBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    quote_number: str
    revision: int = 1
    parent_quote_id: Optional[uuid.UUID] = None
    is_current: bool = True
    status: QuoteStatus = QuoteStatus.DRAFT
    trip_id: Optional[uuid.UUID] = None
    account_holder_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    prepared_by_user_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    aircraft_model_id: Optional[uuid.UUID] = None
    aircraft_id: Optional[uuid.UUID] = None
    currency: str = 'USD'
    subtotal_cents: int = 0
    tax_cents: int = 0
    fees_cents: int = 0
    discount_cents: int = 0
    total_cents: int = 0
    cost_total_cents: int = 0
    valid_until: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    first_viewed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None
    view_count: int = 0
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    decline_reason: Optional[str] = None
    terms: Optional[str] = None
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    pdf_document_id: Optional[uuid.UUID] = None
    esign_envelope_id: Optional[str] = None


class QuoteCreate(QuoteBase):
    pass


class QuoteUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    quote_number: Optional[str] = None
    revision: Optional[int] = None
    parent_quote_id: Optional[uuid.UUID] = None
    is_current: Optional[bool] = None
    status: Optional[QuoteStatus] = None
    trip_id: Optional[uuid.UUID] = None
    account_holder_id: Optional[uuid.UUID] = None
    contact_id: Optional[uuid.UUID] = None
    prepared_by_user_id: Optional[uuid.UUID] = None
    operator_id: Optional[uuid.UUID] = None
    aircraft_model_id: Optional[uuid.UUID] = None
    aircraft_id: Optional[uuid.UUID] = None
    currency: Optional[str] = None
    subtotal_cents: Optional[int] = None
    tax_cents: Optional[int] = None
    fees_cents: Optional[int] = None
    discount_cents: Optional[int] = None
    total_cents: Optional[int] = None
    cost_total_cents: Optional[int] = None
    valid_until: Optional[datetime] = None
    sent_at: Optional[datetime] = None
    first_viewed_at: Optional[datetime] = None
    last_viewed_at: Optional[datetime] = None
    view_count: Optional[int] = None
    accepted_at: Optional[datetime] = None
    declined_at: Optional[datetime] = None
    decline_reason: Optional[str] = None
    terms: Optional[str] = None
    customer_notes: Optional[str] = None
    internal_notes: Optional[str] = None
    pdf_document_id: Optional[uuid.UUID] = None
    esign_envelope_id: Optional[str] = None


class QuoteRead(QuoteBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    margin_cents: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class QuoteList(BaseModel):
    items: list[QuoteRead]
    total: int
    page: int
    page_size: int


class QuoteLineItemBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    quote_id: uuid.UUID
    leg_id: Optional[uuid.UUID] = None
    line_type: LineItemType
    description: str
    quantity: float = 1
    unit: Optional[str] = None
    unit_price_cents: int = 0
    sell_cents: int = 0
    cost_cents: int = 0
    is_taxable: bool = True
    tax_rate: float = 0
    is_pass_through: bool = False
    is_optional: bool = False
    sort_order: int = 0


class QuoteLineItemCreate(QuoteLineItemBase):
    pass


class QuoteLineItemUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    quote_id: Optional[uuid.UUID] = None
    leg_id: Optional[uuid.UUID] = None
    line_type: Optional[LineItemType] = None
    description: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    unit_price_cents: Optional[int] = None
    sell_cents: Optional[int] = None
    cost_cents: Optional[int] = None
    is_taxable: Optional[bool] = None
    tax_rate: Optional[float] = None
    is_pass_through: Optional[bool] = None
    is_optional: Optional[bool] = None
    sort_order: Optional[int] = None


class QuoteLineItemRead(QuoteLineItemBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class QuoteLineItemList(BaseModel):
    items: list[QuoteLineItemRead]
    total: int
    page: int
    page_size: int
