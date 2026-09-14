"""010 - Commerce: Quotes -> Bookings -> Invoices -> Payments

DATA_MODEL.md 3.8.

Quote revisions are immutable (DATA_MODEL 5, "Quote versioning"): a quote is
never mutated after ``sent_at``. An edit inserts ``revision + 1`` with
``parent_quote_id`` pointing back, and flips the old row to
``is_current = false, status = 'superseded'``. The partial unique index
``uq_quotes_current`` guarantees exactly one live revision per quote number,
so the whole negotiation history survives a pricing dispute.

Also closes the circular reference from migration 008: ``trips.accepted_quote_id``
and ``trips.booking_id`` are attached here as DEFERRABLE INITIALLY DEFERRED.

Forward FKs attached in migration 011 (documents):
  * quotes.pdf_document_id
  * bookings.contract_document_id
  * invoices.pdf_document_id

Revision ID: 010
Revises: 009
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import (
    CITEXT,
    grant_app_dml,
    money,
    pgenum,
    std_cols,
    std_indexes,
    TS,
    UUID,
)

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------- quotes
    op.create_table(
        "quotes",
        *std_cols(),
        sa.Column("quote_number", CITEXT(), nullable=False),  # stable across revisions
        sa.Column("revision", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "parent_quote_id",
            UUID,
            sa.ForeignKey("quotes.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", pgenum("quote_status"), nullable=False, server_default="draft"),
        # NULL = speculative quote not yet attached to an itinerary.
        sa.Column(
            "trip_id", UUID, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "contact_id", UUID, sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "prepared_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "operator_id", UUID, sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "aircraft_model_id",
            UUID,
            sa.ForeignKey("aircraft_models.id", ondelete="SET NULL"),
            nullable=True,
        ),  # offered type
        sa.Column(
            "aircraft_id", UUID, sa.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True
        ),  # specific tail, when known
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("subtotal_cents", money(), nullable=False, server_default="0"),
        sa.Column("tax_cents", money(), nullable=False, server_default="0"),
        sa.Column("fees_cents", money(), nullable=False, server_default="0"),
        sa.Column("discount_cents", money(), nullable=False, server_default="0"),
        sa.Column("total_cents", money(), nullable=False, server_default="0"),
        sa.Column("cost_total_cents", money(), nullable=False, server_default="0"),
        sa.Column(
            "margin_cents",
            money(),
            sa.Computed("total_cents - cost_total_cents", persisted=True),
            nullable=True,
        ),
        sa.Column("valid_until", TS(), nullable=True),
        sa.Column("sent_at", TS(), nullable=True),
        sa.Column("first_viewed_at", TS(), nullable=True),
        sa.Column("last_viewed_at", TS(), nullable=True),
        sa.Column("view_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accepted_at", TS(), nullable=True),
        sa.Column("declined_at", TS(), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("terms", sa.Text(), nullable=True),
        sa.Column("customer_notes", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        # FK added in migration 011.
        sa.Column("pdf_document_id", UUID, nullable=True),
        sa.Column("esign_envelope_id", sa.Text(), nullable=True),
        sa.CheckConstraint("parent_quote_id <> id", name="ck_quotes_no_self_parent"),
        sa.CheckConstraint(
            "status <> 'accepted' OR accepted_at IS NOT NULL", name="ck_quotes_accepted_at"
        ),
        sa.CheckConstraint("revision > 0", name="ck_quotes_revision_positive"),
        comment="Customer pricing, immutable per revision. DATA_MODEL.md 3.8.",
    )
    std_indexes("quotes")
    op.create_index(
        "uq_quotes_number_revision",
        "quotes",
        ["client_id", "quote_number", "revision"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Exactly one live revision per quote number.
    op.create_index(
        "uq_quotes_current",
        "quotes",
        ["client_id", "quote_number"],
        unique=True,
        postgresql_where=sa.text("is_current AND deleted_at IS NULL"),
    )
    # At most one accepted quote per trip.
    op.create_index(
        "uq_quotes_accepted_per_trip",
        "quotes",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("status = 'accepted' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_quotes_status_valid",
        "quotes",
        ["client_id", "status", "valid_until"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_quotes_trip", "quotes", ["client_id", "trip_id", sa.text("revision DESC")]
    )
    op.create_index(
        "ix_quotes_account",
        "quotes",
        ["client_id", "account_holder_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_quotes_preparer", "quotes", ["client_id", "prepared_by_user_id", "status"])
    # Expiry sweep: only quotes still in play can expire.
    op.create_index(
        "ix_quotes_expiry_sweep",
        "quotes",
        ["client_id", "valid_until"],
        postgresql_where=sa.text("status IN ('sent','viewed','negotiating')"),
    )

    # ----------------------------------------------------------- quote_line_items
    op.create_table(
        "quote_line_items",
        *std_cols(),
        sa.Column(
            "quote_id", UUID, sa.ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "leg_id", UUID, sa.ForeignKey("legs.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("line_type", pgenum("line_item_type"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.Text(), nullable=True),  # 'hour','leg','pax','night'
        sa.Column("unit_price_cents", money(), nullable=False, server_default="0"),
        sa.Column("sell_cents", money(), nullable=False, server_default="0"),
        # Cost sits next to sell so per-line margin is visible without a join.
        sa.Column("cost_cents", money(), nullable=False, server_default="0"),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tax_rate", sa.Numeric(6, 4), nullable=False, server_default="0"),
        # Billed through at cost, no margin taken.
        sa.Column("is_pass_through", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_optional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("tax_rate >= 0", name="ck_quote_line_items_tax_rate"),
        comment="Quote pricing breakdown. DATA_MODEL.md 3.8.",
    )
    std_indexes("quote_line_items")
    op.create_index(
        "ix_quote_line_items_quote", "quote_line_items", ["client_id", "quote_id", "sort_order"]
    )
    op.create_index("ix_quote_line_items_leg", "quote_line_items", ["client_id", "leg_id"])
    op.create_index("ix_quote_line_items_type", "quote_line_items", ["client_id", "line_type"])

    # -------------------------------------------------------------------- bookings
    op.create_table(
        "bookings",
        *std_cols(),
        sa.Column("booking_number", CITEXT(), nullable=False),
        sa.Column(
            "trip_id", UUID, sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "quote_id", UUID, sa.ForeignKey("quotes.id", ondelete="RESTRICT"), nullable=False
        ),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", pgenum("booking_status"), nullable=False, server_default="pending"),
        sa.Column(
            "operator_id", UUID, sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("operator_confirmation_ref", sa.Text(), nullable=True),
        # FK added in migration 011.
        sa.Column("contract_document_id", UUID, nullable=True),
        sa.Column(
            "signed_by_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("esign_envelope_id", sa.Text(), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("total_cents", money(), nullable=False, server_default="0"),
        sa.Column("cost_cents", money(), nullable=False, server_default="0"),
        sa.Column(
            "margin_cents",
            money(),
            sa.Computed("total_cents - cost_cents", persisted=True),
            nullable=True,
        ),
        sa.Column("deposit_required_cents", money(), nullable=False, server_default="0"),
        sa.Column("deposit_due_at", TS(), nullable=True),
        sa.Column("deposit_received_at", TS(), nullable=True),
        sa.Column("confirmed_at", TS(), nullable=True),
        sa.Column("contract_sent_at", TS(), nullable=True),
        sa.Column("contract_signed_at", TS(), nullable=True),
        sa.Column("cancelled_at", TS(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_policy", sa.Text(), nullable=True),
        sa.Column("cancellation_fee_cents", money(), nullable=False, server_default="0"),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL", name="ck_bookings_cancelled_at"
        ),
        comment="Confirmed sale of a trip. DATA_MODEL.md 3.8.",
    )
    std_indexes("bookings")
    op.create_index(
        "uq_bookings_number",
        "bookings",
        ["client_id", "booking_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # One live booking per trip; cancelled ones stay as history.
    op.create_index(
        "uq_bookings_live_per_trip",
        "bookings",
        ["trip_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'cancelled' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_bookings_status",
        "bookings",
        ["client_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_bookings_account",
        "bookings",
        ["client_id", "account_holder_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_bookings_operator", "bookings", ["client_id", "operator_id"])
    # Deposit chase list.
    op.create_index(
        "ix_bookings_deposit_due",
        "bookings",
        ["client_id", "deposit_due_at"],
        postgresql_where=sa.text("deposit_received_at IS NULL"),
    )

    # -------------------------------------------------------------------- invoices
    op.create_table(
        "invoices",
        *std_cols(),
        sa.Column("invoice_number", CITEXT(), nullable=False),
        sa.Column("invoice_type", pgenum("invoice_type"), nullable=False, server_default="full"),
        sa.Column("status", pgenum("invoice_status"), nullable=False, server_default="draft"),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "booking_id", UUID, sa.ForeignKey("bookings.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "trip_id", UUID, sa.ForeignKey("trips.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column(
            "parent_invoice_id",
            UUID,
            sa.ForeignKey("invoices.id", ondelete="RESTRICT"),
            nullable=True,
        ),  # credit notes point at what they credit
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "payment_terms",
            pgenum("payment_terms"),
            nullable=False,
            server_default="due_on_receipt",
        ),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        # Captured at issue time so historical totals do not drift with FX.
        sa.Column("exchange_rate", sa.Numeric(16, 8), nullable=False, server_default="1"),
        sa.Column("subtotal_cents", money(), nullable=False, server_default="0"),
        sa.Column("tax_cents", money(), nullable=False, server_default="0"),
        sa.Column("total_cents", money(), nullable=False, server_default="0"),
        # Materialized from payments; reconciled nightly.
        sa.Column("amount_paid_cents", money(), nullable=False, server_default="0"),
        sa.Column(
            "balance_cents",
            money(),
            sa.Computed("total_cents - amount_paid_cents", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "billing_address_id",
            UUID,
            sa.ForeignKey("addresses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # FK added in migration 011.
        sa.Column("pdf_document_id", UUID, nullable=True),
        sa.Column("sent_at", TS(), nullable=True),
        sa.Column("paid_at", TS(), nullable=True),
        sa.Column("voided_at", TS(), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),  # QuickBooks / Xero id
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status <> 'void' OR (voided_at IS NOT NULL AND void_reason IS NOT NULL)",
            name="ck_invoices_void_reason",
        ),
        sa.CheckConstraint(
            "invoice_type <> 'credit_note' OR parent_invoice_id IS NOT NULL",
            name="ck_invoices_credit_note_parent",
        ),
        sa.CheckConstraint("parent_invoice_id <> id", name="ck_invoices_no_self_parent"),
        sa.CheckConstraint(
            "due_date IS NULL OR issue_date IS NULL OR due_date >= issue_date",
            name="ck_invoices_date_order",
        ),
        sa.CheckConstraint("exchange_rate > 0", name="ck_invoices_fx_positive"),
        comment="Accounts receivable. DATA_MODEL.md 3.8.",
    )
    std_indexes("invoices")
    op.create_index(
        "uq_invoices_number",
        "invoices",
        ["client_id", "invoice_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_invoices_external",
        "invoices",
        ["client_id", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_invoices_status_due",
        "invoices",
        ["client_id", "status", "due_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_invoices_account",
        "invoices",
        ["client_id", "account_holder_id", sa.text("issue_date DESC")],
    )
    # AR aging -- only unsettled invoices age.
    op.create_index(
        "ix_invoices_aging",
        "invoices",
        ["client_id", "due_date"],
        postgresql_where=sa.text(
            "status IN ('issued','sent','partially_paid','overdue')"
        ),
    )
    op.create_index("ix_invoices_booking", "invoices", ["client_id", "booking_id"])

    # --------------------------------------------------------- invoice_line_items
    op.create_table(
        "invoice_line_items",
        *std_cols(),
        sa.Column(
            "invoice_id", UUID, sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False
        ),
        # Provenance: which quote line this was billed from.
        sa.Column(
            "quote_line_item_id",
            UUID,
            sa.ForeignKey("quote_line_items.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "leg_id", UUID, sa.ForeignKey("legs.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("line_type", pgenum("line_item_type"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=False, server_default="1"),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("unit_price_cents", money(), nullable=False, server_default="0"),
        sa.Column("amount_cents", money(), nullable=False, server_default="0"),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("tax_rate", sa.Numeric(6, 4), nullable=False, server_default="0"),
        sa.Column("tax_cents", money(), nullable=False, server_default="0"),
        sa.Column("gl_account_code", sa.Text(), nullable=True),  # accounting export
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.CheckConstraint("tax_rate >= 0", name="ck_invoice_line_items_tax_rate"),
        comment="Invoice breakdown. DATA_MODEL.md 3.8.",
    )
    std_indexes("invoice_line_items")
    op.create_index(
        "ix_invoice_line_items_inv",
        "invoice_line_items",
        ["client_id", "invoice_id", "sort_order"],
    )
    op.create_index("ix_invoice_line_items_type", "invoice_line_items", ["client_id", "line_type"])

    # -------------------------------------------------------------------- payments
    op.create_table(
        "payments",
        *std_cols(),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # NULL = money on account, not yet applied to a specific invoice.
        sa.Column(
            "invoice_id", UUID, sa.ForeignKey("invoices.id", ondelete="RESTRICT"), nullable=True
        ),
        sa.Column("method", pgenum("payment_method"), nullable=False),
        sa.Column("status", pgenum("payment_status"), nullable=False, server_default="pending"),
        # Negative for refunds, which is why the CHECK is <> 0 rather than > 0.
        sa.Column("amount_cents", money(), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("exchange_rate", sa.Numeric(16, 8), nullable=False, server_default="1"),
        sa.Column("fee_cents", money(), nullable=False, server_default="0"),
        sa.Column("received_at", TS(), nullable=False),
        sa.Column("cleared_at", TS(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),  # wire ref, check number
        sa.Column("processor", sa.Text(), nullable=True),
        sa.Column("processor_txn_id", sa.Text(), nullable=True),
        sa.Column(
            "refund_of_payment_id",
            UUID,
            sa.ForeignKey("payments.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount_cents <> 0", name="ck_payments_amount_nonzero"),
        sa.CheckConstraint("refund_of_payment_id <> id", name="ck_payments_no_self_refund"),
        sa.CheckConstraint("exchange_rate > 0", name="ck_payments_fx_positive"),
        comment="Cash received and refunded. DATA_MODEL.md 3.8.",
    )
    std_indexes("payments")
    # Webhook idempotency: a processor must never be double-recorded.
    op.create_index(
        "uq_payments_processor_txn",
        "payments",
        ["processor", "processor_txn_id"],
        unique=True,
        postgresql_where=sa.text("processor_txn_id IS NOT NULL"),
    )
    op.create_index("ix_payments_invoice", "payments", ["client_id", "invoice_id"])
    op.create_index(
        "ix_payments_account",
        "payments",
        ["client_id", "account_holder_id", sa.text("received_at DESC")],
    )
    op.create_index(
        "ix_payments_status",
        "payments",
        ["client_id", "status", "received_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ------------------------- deferred circular FKs from migration 008 -----------
    # DEFERRABLE INITIALLY DEFERRED: trip -> quote -> booking can be inserted in
    # one transaction without ordering gymnastics. The child-side trip_id columns
    # remain the authoritative, immediately-checked edges.
    op.create_foreign_key(
        "fk_trips_accepted_quote",
        "trips",
        "quotes",
        ["accepted_quote_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )
    op.create_foreign_key(
        "fk_trips_booking",
        "trips",
        "bookings",
        ["booking_id"],
        ["id"],
        ondelete="SET NULL",
        deferrable=True,
        initially="DEFERRED",
    )

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml(
        "quotes",
        "quote_line_items",
        "bookings",
        "invoices",
        "invoice_line_items",
        "payments",
    )


def downgrade() -> None:
    op.drop_constraint("fk_trips_booking", "trips", type_="foreignkey")
    op.drop_constraint("fk_trips_accepted_quote", "trips", type_="foreignkey")
    op.drop_table("payments")
    op.drop_table("invoice_line_items")
    op.drop_table("invoices")
    op.drop_table("bookings")
    op.drop_table("quote_line_items")
    op.drop_table("quotes")
