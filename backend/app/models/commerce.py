"""Commerce: Quotes -> Bookings -> Invoices -> Payments (DATA_MODEL.md 3.8)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CHAR, CheckConstraint, Column, Computed, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, Text, text, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import BookingStatus, InvoiceStatus, InvoiceType, LineItemType, PaymentMethod, PaymentStatus, PaymentTerms, QuoteStatus

if TYPE_CHECKING:
    from .crm import AccountHolder
    from .trips import Trip


class Quote(BitluxBase, TenantScopedMixin, table=True):
    """Customer pricing, immutable per revision. DATA_MODEL.md 3.8."""
    __tablename__ = "quotes"
    __table_args__ = (
        *tenant_indexes("quotes"),
        Index("uq_quotes_number_revision", "client_id", "quote_number", "revision", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_quotes_current", "client_id", "quote_number", unique=True, postgresql_where=text("is_current AND deleted_at IS NULL")),
        Index("uq_quotes_accepted_per_trip", "trip_id", unique=True, postgresql_where=text("status = 'accepted' AND deleted_at IS NULL")),
        Index("ix_quotes_status_valid", "client_id", "status", "valid_until", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_quotes_trip", "client_id", "trip_id", text("revision DESC")),
        Index("ix_quotes_account", "client_id", "account_holder_id", text("created_at DESC")),
        Index("ix_quotes_preparer", "client_id", "prepared_by_user_id", "status"),
        Index("ix_quotes_expiry_sweep", "client_id", "valid_until", postgresql_where=text("status IN ('sent','viewed','negotiating')")),
        CheckConstraint("parent_quote_id <> id", name="ck_quotes_no_self_parent"),
        CheckConstraint("status <> 'accepted' OR accepted_at IS NOT NULL", name="ck_quotes_accepted_at"),
        CheckConstraint("revision > 0", name="ck_quotes_revision_positive"),
        {"comment": "Customer pricing, immutable per revision. DATA_MODEL.md 3.8."},
    )

    quote_number: str = Field(sa_column=Column("quote_number", CITEXT, nullable=False))
    revision: int = Field(default=1, sa_column=Column("revision", SmallInteger, nullable=False, server_default="1"))
    parent_quote_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("parent_quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="SET NULL")))
    is_current: bool = Field(default=True, sa_column=Column("is_current", Boolean, nullable=False, server_default=text("true")))
    status: QuoteStatus = Field(default=QuoteStatus.DRAFT, sa_column=Column("status", pg_enum(QuoteStatus), nullable=False, server_default="draft"))
    trip_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("trip_id", UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE")))
    account_holder_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="RESTRICT")))
    contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    prepared_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("prepared_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    operator_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="SET NULL")))
    aircraft_model_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("aircraft_model_id", UUID(as_uuid=True), ForeignKey("aircraft_models.id", ondelete="SET NULL")))
    aircraft_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("aircraft_id", UUID(as_uuid=True), ForeignKey("aircraft.id", ondelete="SET NULL")))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    subtotal_cents: int = Field(default=0, sa_column=Column("subtotal_cents", BigInteger, nullable=False, server_default="0"))
    tax_cents: int = Field(default=0, sa_column=Column("tax_cents", BigInteger, nullable=False, server_default="0"))
    fees_cents: int = Field(default=0, sa_column=Column("fees_cents", BigInteger, nullable=False, server_default="0"))
    discount_cents: int = Field(default=0, sa_column=Column("discount_cents", BigInteger, nullable=False, server_default="0"))
    total_cents: int = Field(default=0, sa_column=Column("total_cents", BigInteger, nullable=False, server_default="0"))
    cost_total_cents: int = Field(default=0, sa_column=Column("cost_total_cents", BigInteger, nullable=False, server_default="0"))
    margin_cents: Optional[int] = Field(default=None, sa_column=Column("margin_cents", BigInteger, Computed("total_cents - cost_total_cents", persisted=True)))
    valid_until: Optional[datetime] = Field(default=None, sa_column=Column("valid_until", TIMESTAMP(timezone=True)))
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column("sent_at", TIMESTAMP(timezone=True)))
    first_viewed_at: Optional[datetime] = Field(default=None, sa_column=Column("first_viewed_at", TIMESTAMP(timezone=True)))
    last_viewed_at: Optional[datetime] = Field(default=None, sa_column=Column("last_viewed_at", TIMESTAMP(timezone=True)))
    view_count: int = Field(default=0, sa_column=Column("view_count", Integer, nullable=False, server_default="0"))
    accepted_at: Optional[datetime] = Field(default=None, sa_column=Column("accepted_at", TIMESTAMP(timezone=True)))
    declined_at: Optional[datetime] = Field(default=None, sa_column=Column("declined_at", TIMESTAMP(timezone=True)))
    decline_reason: Optional[str] = Field(default=None, sa_column=Column("decline_reason", Text))
    terms: Optional[str] = Field(default=None, sa_column=Column("terms", Text))
    customer_notes: Optional[str] = Field(default=None, sa_column=Column("customer_notes", Text))
    internal_notes: Optional[str] = Field(default=None, sa_column=Column("internal_notes", Text))
    pdf_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("pdf_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_quotes_pdf")))
    esign_envelope_id: Optional[str] = Field(default=None, sa_column=Column("esign_envelope_id", Text))

    trip: Optional["Trip"] = Relationship(back_populates="quotes", sa_relationship_kwargs={"foreign_keys": "[Quote.trip_id]"})
    line_items: list["QuoteLineItem"] = Relationship(back_populates="quote", cascade_delete=True, sa_relationship_kwargs={"order_by": "QuoteLineItem.sort_order"})
    bookings: list["Booking"] = Relationship(back_populates="quote")


class QuoteLineItem(BitluxBase, TenantScopedMixin, table=True):
    """Quote pricing breakdown. DATA_MODEL.md 3.8."""
    __tablename__ = "quote_line_items"
    __table_args__ = (
        *tenant_indexes("quote_line_items"),
        Index("ix_quote_line_items_quote", "client_id", "quote_id", "sort_order"),
        Index("ix_quote_line_items_leg", "client_id", "leg_id"),
        Index("ix_quote_line_items_type", "client_id", "line_type"),
        CheckConstraint("tax_rate >= 0", name="ck_quote_line_items_tax_rate"),
        {"comment": "Quote pricing breakdown. DATA_MODEL.md 3.8."},
    )

    quote_id: uuid.UUID = Field(sa_column=Column("quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False))
    leg_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("leg_id", UUID(as_uuid=True), ForeignKey("legs.id", ondelete="SET NULL")))
    line_type: LineItemType = Field(sa_column=Column("line_type", pg_enum(LineItemType), nullable=False))
    description: str = Field(sa_column=Column("description", Text, nullable=False))
    quantity: Decimal = Field(default=Decimal("1"), sa_column=Column("quantity", Numeric(12, 3), nullable=False, server_default="1"))
    unit: Optional[str] = Field(default=None, sa_column=Column("unit", Text))
    unit_price_cents: int = Field(default=0, sa_column=Column("unit_price_cents", BigInteger, nullable=False, server_default="0"))
    sell_cents: int = Field(default=0, sa_column=Column("sell_cents", BigInteger, nullable=False, server_default="0"))
    cost_cents: int = Field(default=0, sa_column=Column("cost_cents", BigInteger, nullable=False, server_default="0"))
    is_taxable: bool = Field(default=True, sa_column=Column("is_taxable", Boolean, nullable=False, server_default=text("true")))
    tax_rate: Decimal = Field(default=Decimal("0"), sa_column=Column("tax_rate", Numeric(6, 4), nullable=False, server_default="0"))
    is_pass_through: bool = Field(default=False, sa_column=Column("is_pass_through", Boolean, nullable=False, server_default=text("false")))
    is_optional: bool = Field(default=False, sa_column=Column("is_optional", Boolean, nullable=False, server_default=text("false")))
    sort_order: int = Field(default=0, sa_column=Column("sort_order", SmallInteger, nullable=False, server_default="0"))

    quote: Optional["Quote"] = Relationship(back_populates="line_items")


class Booking(BitluxBase, TenantScopedMixin, table=True):
    """Confirmed sale of a trip. DATA_MODEL.md 3.8."""
    __tablename__ = "bookings"
    __table_args__ = (
        *tenant_indexes("bookings"),
        Index("uq_bookings_number", "client_id", "booking_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_bookings_live_per_trip", "trip_id", unique=True, postgresql_where=text("status <> 'cancelled' AND deleted_at IS NULL")),
        Index("ix_bookings_status", "client_id", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_bookings_account", "client_id", "account_holder_id", text("created_at DESC")),
        Index("ix_bookings_operator", "client_id", "operator_id"),
        Index("ix_bookings_deposit_due", "client_id", "deposit_due_at", postgresql_where=text("deposit_received_at IS NULL")),
        CheckConstraint("status <> 'cancelled' OR cancelled_at IS NOT NULL", name="ck_bookings_cancelled_at"),
        {"comment": "Confirmed sale of a trip. DATA_MODEL.md 3.8."},
    )

    booking_number: str = Field(sa_column=Column("booking_number", CITEXT, nullable=False))
    trip_id: uuid.UUID = Field(sa_column=Column("trip_id", UUID(as_uuid=True), ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False))
    quote_id: uuid.UUID = Field(sa_column=Column("quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="RESTRICT"), nullable=False))
    account_holder_id: uuid.UUID = Field(sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="RESTRICT"), nullable=False))
    status: BookingStatus = Field(default=BookingStatus.PENDING, sa_column=Column("status", pg_enum(BookingStatus), nullable=False, server_default="pending"))
    operator_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="SET NULL")))
    operator_confirmation_ref: Optional[str] = Field(default=None, sa_column=Column("operator_confirmation_ref", Text))
    contract_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("contract_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_bookings_contract")))
    signed_by_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("signed_by_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    esign_envelope_id: Optional[str] = Field(default=None, sa_column=Column("esign_envelope_id", Text))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    total_cents: int = Field(default=0, sa_column=Column("total_cents", BigInteger, nullable=False, server_default="0"))
    cost_cents: int = Field(default=0, sa_column=Column("cost_cents", BigInteger, nullable=False, server_default="0"))
    margin_cents: Optional[int] = Field(default=None, sa_column=Column("margin_cents", BigInteger, Computed("total_cents - cost_cents", persisted=True)))
    deposit_required_cents: int = Field(default=0, sa_column=Column("deposit_required_cents", BigInteger, nullable=False, server_default="0"))
    deposit_due_at: Optional[datetime] = Field(default=None, sa_column=Column("deposit_due_at", TIMESTAMP(timezone=True)))
    deposit_received_at: Optional[datetime] = Field(default=None, sa_column=Column("deposit_received_at", TIMESTAMP(timezone=True)))
    confirmed_at: Optional[datetime] = Field(default=None, sa_column=Column("confirmed_at", TIMESTAMP(timezone=True)))
    contract_sent_at: Optional[datetime] = Field(default=None, sa_column=Column("contract_sent_at", TIMESTAMP(timezone=True)))
    contract_signed_at: Optional[datetime] = Field(default=None, sa_column=Column("contract_signed_at", TIMESTAMP(timezone=True)))
    cancelled_at: Optional[datetime] = Field(default=None, sa_column=Column("cancelled_at", TIMESTAMP(timezone=True)))
    cancellation_reason: Optional[str] = Field(default=None, sa_column=Column("cancellation_reason", Text))
    cancellation_policy: Optional[str] = Field(default=None, sa_column=Column("cancellation_policy", Text))
    cancellation_fee_cents: int = Field(default=0, sa_column=Column("cancellation_fee_cents", BigInteger, nullable=False, server_default="0"))

    trip: Optional["Trip"] = Relationship(back_populates="bookings", sa_relationship_kwargs={"foreign_keys": "[Booking.trip_id]"})
    quote: Optional["Quote"] = Relationship(back_populates="bookings")
    invoices: list["Invoice"] = Relationship(back_populates="booking")


class Invoice(BitluxBase, TenantScopedMixin, table=True):
    """Accounts receivable. DATA_MODEL.md 3.8."""
    __tablename__ = "invoices"
    __table_args__ = (
        *tenant_indexes("invoices"),
        Index("uq_invoices_number", "client_id", "invoice_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_invoices_external", "client_id", "external_ref", unique=True, postgresql_where=text("external_ref IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_invoices_status_due", "client_id", "status", "due_date", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_invoices_account", "client_id", "account_holder_id", text("issue_date DESC")),
        Index("ix_invoices_aging", "client_id", "due_date", postgresql_where=text("status IN ('issued','sent','partially_paid','overdue')")),
        Index("ix_invoices_booking", "client_id", "booking_id"),
        CheckConstraint("status <> 'void' OR (voided_at IS NOT NULL AND void_reason IS NOT NULL)", name="ck_invoices_void_reason"),
        CheckConstraint("invoice_type <> 'credit_note' OR parent_invoice_id IS NOT NULL", name="ck_invoices_credit_note_parent"),
        CheckConstraint("parent_invoice_id <> id", name="ck_invoices_no_self_parent"),
        CheckConstraint("due_date IS NULL OR issue_date IS NULL OR due_date >= issue_date", name="ck_invoices_date_order"),
        CheckConstraint("exchange_rate > 0", name="ck_invoices_fx_positive"),
        {"comment": "Accounts receivable. DATA_MODEL.md 3.8."},
    )

    invoice_number: str = Field(sa_column=Column("invoice_number", CITEXT, nullable=False))
    invoice_type: InvoiceType = Field(default=InvoiceType.FULL, sa_column=Column("invoice_type", pg_enum(InvoiceType), nullable=False, server_default="full"))
    status: InvoiceStatus = Field(default=InvoiceStatus.DRAFT, sa_column=Column("status", pg_enum(InvoiceStatus), nullable=False, server_default="draft"))
    account_holder_id: uuid.UUID = Field(sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="RESTRICT"), nullable=False))
    booking_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("booking_id", UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="RESTRICT")))
    trip_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("trip_id", UUID(as_uuid=True), ForeignKey("trips.id", ondelete="RESTRICT")))
    parent_invoice_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("parent_invoice_id", UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT")))
    issue_date: Optional[date] = Field(default=None, sa_column=Column("issue_date", Date))
    due_date: Optional[date] = Field(default=None, sa_column=Column("due_date", Date))
    payment_terms: PaymentTerms = Field(default=PaymentTerms.DUE_ON_RECEIPT, sa_column=Column("payment_terms", pg_enum(PaymentTerms), nullable=False, server_default="due_on_receipt"))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    exchange_rate: Decimal = Field(default=Decimal("1"), sa_column=Column("exchange_rate", Numeric(16, 8), nullable=False, server_default="1"))
    subtotal_cents: int = Field(default=0, sa_column=Column("subtotal_cents", BigInteger, nullable=False, server_default="0"))
    tax_cents: int = Field(default=0, sa_column=Column("tax_cents", BigInteger, nullable=False, server_default="0"))
    total_cents: int = Field(default=0, sa_column=Column("total_cents", BigInteger, nullable=False, server_default="0"))
    amount_paid_cents: int = Field(default=0, sa_column=Column("amount_paid_cents", BigInteger, nullable=False, server_default="0"))
    balance_cents: Optional[int] = Field(default=None, sa_column=Column("balance_cents", BigInteger, Computed("total_cents - amount_paid_cents", persisted=True)))
    billing_address_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("billing_address_id", UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL")))
    pdf_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("pdf_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_invoices_pdf")))
    sent_at: Optional[datetime] = Field(default=None, sa_column=Column("sent_at", TIMESTAMP(timezone=True)))
    paid_at: Optional[datetime] = Field(default=None, sa_column=Column("paid_at", TIMESTAMP(timezone=True)))
    voided_at: Optional[datetime] = Field(default=None, sa_column=Column("voided_at", TIMESTAMP(timezone=True)))
    void_reason: Optional[str] = Field(default=None, sa_column=Column("void_reason", Text))
    external_ref: Optional[str] = Field(default=None, sa_column=Column("external_ref", Text))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    account_holder: Optional["AccountHolder"] = Relationship(back_populates="invoices")
    booking: Optional["Booking"] = Relationship(back_populates="invoices")
    line_items: list["InvoiceLineItem"] = Relationship(back_populates="invoice", cascade_delete=True, sa_relationship_kwargs={"order_by": "InvoiceLineItem.sort_order"})
    payments: list["Payment"] = Relationship(back_populates="invoice")


class InvoiceLineItem(BitluxBase, TenantScopedMixin, table=True):
    """Invoice breakdown. DATA_MODEL.md 3.8."""
    __tablename__ = "invoice_line_items"
    __table_args__ = (
        *tenant_indexes("invoice_line_items"),
        Index("ix_invoice_line_items_inv", "client_id", "invoice_id", "sort_order"),
        Index("ix_invoice_line_items_type", "client_id", "line_type"),
        CheckConstraint("tax_rate >= 0", name="ck_invoice_line_items_tax_rate"),
        {"comment": "Invoice breakdown. DATA_MODEL.md 3.8."},
    )

    invoice_id: uuid.UUID = Field(sa_column=Column("invoice_id", UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False))
    quote_line_item_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("quote_line_item_id", UUID(as_uuid=True), ForeignKey("quote_line_items.id", ondelete="SET NULL")))
    leg_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("leg_id", UUID(as_uuid=True), ForeignKey("legs.id", ondelete="SET NULL")))
    line_type: LineItemType = Field(sa_column=Column("line_type", pg_enum(LineItemType), nullable=False))
    description: str = Field(sa_column=Column("description", Text, nullable=False))
    quantity: Decimal = Field(default=Decimal("1"), sa_column=Column("quantity", Numeric(12, 3), nullable=False, server_default="1"))
    unit: Optional[str] = Field(default=None, sa_column=Column("unit", Text))
    unit_price_cents: int = Field(default=0, sa_column=Column("unit_price_cents", BigInteger, nullable=False, server_default="0"))
    amount_cents: int = Field(default=0, sa_column=Column("amount_cents", BigInteger, nullable=False, server_default="0"))
    is_taxable: bool = Field(default=True, sa_column=Column("is_taxable", Boolean, nullable=False, server_default=text("true")))
    tax_rate: Decimal = Field(default=Decimal("0"), sa_column=Column("tax_rate", Numeric(6, 4), nullable=False, server_default="0"))
    tax_cents: int = Field(default=0, sa_column=Column("tax_cents", BigInteger, nullable=False, server_default="0"))
    gl_account_code: Optional[str] = Field(default=None, sa_column=Column("gl_account_code", Text))
    sort_order: int = Field(default=0, sa_column=Column("sort_order", SmallInteger, nullable=False, server_default="0"))

    invoice: Optional["Invoice"] = Relationship(back_populates="line_items")


class Payment(BitluxBase, TenantScopedMixin, table=True):
    """Cash received and refunded. DATA_MODEL.md 3.8."""
    __tablename__ = "payments"
    __table_args__ = (
        *tenant_indexes("payments"),
        Index("uq_payments_processor_txn", "processor", "processor_txn_id", unique=True, postgresql_where=text("processor_txn_id IS NOT NULL")),
        Index("ix_payments_invoice", "client_id", "invoice_id"),
        Index("ix_payments_account", "client_id", "account_holder_id", text("received_at DESC")),
        Index("ix_payments_status", "client_id", "status", "received_at", postgresql_where=text("deleted_at IS NULL")),
        CheckConstraint("amount_cents <> 0", name="ck_payments_amount_nonzero"),
        CheckConstraint("refund_of_payment_id <> id", name="ck_payments_no_self_refund"),
        CheckConstraint("exchange_rate > 0", name="ck_payments_fx_positive"),
        {"comment": "Cash received and refunded. DATA_MODEL.md 3.8."},
    )

    account_holder_id: uuid.UUID = Field(sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="RESTRICT"), nullable=False))
    invoice_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("invoice_id", UUID(as_uuid=True), ForeignKey("invoices.id", ondelete="RESTRICT")))
    method: PaymentMethod = Field(sa_column=Column("method", pg_enum(PaymentMethod), nullable=False))
    status: PaymentStatus = Field(default=PaymentStatus.PENDING, sa_column=Column("status", pg_enum(PaymentStatus), nullable=False, server_default="pending"))
    amount_cents: int = Field(sa_column=Column("amount_cents", BigInteger, nullable=False))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    exchange_rate: Decimal = Field(default=Decimal("1"), sa_column=Column("exchange_rate", Numeric(16, 8), nullable=False, server_default="1"))
    fee_cents: int = Field(default=0, sa_column=Column("fee_cents", BigInteger, nullable=False, server_default="0"))
    received_at: datetime = Field(sa_column=Column("received_at", TIMESTAMP(timezone=True), nullable=False))
    cleared_at: Optional[datetime] = Field(default=None, sa_column=Column("cleared_at", TIMESTAMP(timezone=True)))
    reference: Optional[str] = Field(default=None, sa_column=Column("reference", Text))
    processor: Optional[str] = Field(default=None, sa_column=Column("processor", Text))
    processor_txn_id: Optional[str] = Field(default=None, sa_column=Column("processor_txn_id", Text))
    refund_of_payment_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("refund_of_payment_id", UUID(as_uuid=True), ForeignKey("payments.id", ondelete="RESTRICT")))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    account_holder: Optional["AccountHolder"] = Relationship(back_populates="payments")
    invoice: Optional["Invoice"] = Relationship(back_populates="payments")
