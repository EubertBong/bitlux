"""005 - CRM spine: Segments -> Contacts -> Passengers -> Account Holders

DATA_MODEL.md 3.2.

The core graph of the CRM. Reading the chain: a segment groups contacts; a
contact may have zero or one passenger identity (and a passenger may exist with
no contact record at all -- a guest); passengers link M:N to account holders,
the entity that actually pays.

Two FKs point forward and are attached later:
  * travel_documents.crew_member_id   -> crew_members (migration 007)
  * travel_documents.scan_document_id -> documents    (migration 011)

Revision ID: 005
Revises: 004
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from migration_helpers import (
    CITEXT,
    grant_app_dml,
    JSONB,
    LTREE,
    money,
    pgenum,
    std_cols,
    std_indexes,
    TS,
    tsv,
    UUID,
)

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # -------------------------------------------------------------------- segments
    op.create_table(
        "segments",
        *std_cols(),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("code", CITEXT(), nullable=True),
        sa.Column(
            "segment_type", pgenum("segment_type"), nullable=False, server_default="other"
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "parent_segment_id",
            UUID,
            sa.ForeignKey("segments.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("path", LTREE(), nullable=True),  # materialized ancestry
        sa.Column("color", sa.Text(), nullable=True),  # #RRGGBB for UI
        # is_auto segments derive membership from `criteria` rather than an
        # explicit contacts.segment_id assignment.
        sa.Column("is_auto", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("criteria", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.CheckConstraint("parent_segment_id <> id", name="ck_segments_no_self_parent"),
        comment="Contact segmentation, hierarchical. DATA_MODEL.md 3.2.",
    )
    std_indexes("segments")
    op.create_index(
        "uq_segments_client_name",
        "segments",
        ["client_id", sa.text("lower(name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_segments_client_code",
        "segments",
        ["client_id", "code"],
        unique=True,
        postgresql_where=sa.text("code IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index("ix_segments_parent", "segments", ["client_id", "parent_segment_id"])
    op.execute("CREATE INDEX ix_segments_path ON segments USING GIST (path)")

    # -------------------------------------------------------------------- contacts
    op.create_table(
        "contacts",
        *std_cols(),
        sa.Column(
            "segment_id", UUID, sa.ForeignKey("segments.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "contact_type", pgenum("contact_type"), nullable=False, server_default="individual"
        ),
        sa.Column("status", pgenum("contact_status"), nullable=False, server_default="lead"),
        sa.Column("salutation", sa.Text(), nullable=True),
        sa.Column("first_name", sa.Text(), nullable=True),
        sa.Column("middle_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Text(), nullable=True),
        # Person full name or company name -- what the UI shows everywhere.
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("company_name", sa.Text(), nullable=True),
        sa.Column("job_title", sa.Text(), nullable=True),
        sa.Column(
            "parent_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),  # employee -> company
        sa.Column(
            "referred_by_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),  # responsible broker
        sa.Column("source", pgenum("lead_source"), nullable=False, server_default="other"),
        # Denormalized from contact_channels for list views and search.
        sa.Column("primary_email", CITEXT(), nullable=True),
        sa.Column("primary_phone", sa.Text(), nullable=True),
        sa.Column("preferred_language", sa.Text(), nullable=True),
        # Materialized rollups -- reporting conveniences, never the source of
        # truth (DATA_MODEL 5, "Materialized rollups").
        sa.Column("lifetime_value_cents", money(), nullable=False, server_default="0"),
        sa.Column("trip_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity_at", TS(), nullable=True),
        sa.Column("do_not_contact", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("vip_notes", sa.Text(), nullable=True),
        sa.Column("preferences", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "search_tsv",
            pg.TSVECTOR(),
            sa.Computed(
                tsv("display_name", "company_name", "primary_email", "primary_phone"),
                persisted=True,
            ),
            nullable=True,
        ),
        sa.CheckConstraint(
            "contact_type <> 'company' OR company_name IS NOT NULL",
            name="ck_contacts_company_needs_name",
        ),
        sa.CheckConstraint(
            "contact_type <> 'individual' OR last_name IS NOT NULL",
            name="ck_contacts_individual_needs_last_name",
        ),
        sa.CheckConstraint("parent_contact_id <> id", name="ck_contacts_no_self_parent"),
        sa.CheckConstraint("referred_by_contact_id <> id", name="ck_contacts_no_self_referral"),
        comment="People and companies in the CRM. DATA_MODEL.md 3.2.",
    )
    std_indexes("contacts")
    op.create_index(
        "ix_contacts_status",
        "contacts",
        ["client_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contacts_segment",
        "contacts",
        ["client_id", "segment_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_contacts_owner",
        "contacts",
        ["client_id", "owner_user_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_contacts_email", "contacts", ["client_id", "primary_email"])
    op.create_index("ix_contacts_parent", "contacts", ["client_id", "parent_contact_id"])
    op.create_index(
        "ix_contacts_last_activity",
        "contacts",
        ["client_id", sa.text("last_activity_at DESC")],
    )
    op.create_index("ix_contacts_search", "contacts", ["search_tsv"], postgresql_using="gin")

    # ------------------------------------------------------------ contact_channels
    op.create_table(
        "contact_channels",
        *std_cols(),
        sa.Column(
            "contact_id", UUID, sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("channel_type", pgenum("channel_type"), nullable=False),
        sa.Column("value", CITEXT(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),  # 'work', 'assistant', 'yacht'
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("verified_at", TS(), nullable=True),
        sa.Column("opted_out_at", TS(), nullable=True),
        comment="A contact's emails / phones / handles. DATA_MODEL.md 3.2.",
    )
    std_indexes("contact_channels")
    op.create_index(
        "uq_contact_channels_value",
        "contact_channels",
        ["contact_id", "channel_type", "value"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # At most one primary per channel type per contact.
    op.create_index(
        "uq_contact_channels_primary",
        "contact_channels",
        ["contact_id", "channel_type"],
        unique=True,
        postgresql_where=sa.text("is_primary AND deleted_at IS NULL"),
    )
    op.create_index("ix_contact_channels_value", "contact_channels", ["client_id", "value"])

    # ------------------------------------------------------------------- addresses
    # POLYMORPHIC: owner_id has no FK. Integrity is enforced by the trigger added
    # in migration 013 (DATA_MODEL 5, "Polymorphism").
    op.create_table(
        "addresses",
        *std_cols(),
        sa.Column("owner_type", pgenum("entity_type"), nullable=False),
        sa.Column("owner_id", UUID, nullable=False),
        sa.Column(
            "address_type", pgenum("address_type"), nullable=False, server_default="other"
        ),
        sa.Column("line1", sa.Text(), nullable=False),
        sa.Column("line2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("region", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.Text(), nullable=True),
        sa.Column("country_code", sa.CHAR(2), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        comment="Polymorphic postal addresses. DATA_MODEL.md 3.2.",
    )
    std_indexes("addresses")
    op.create_index(
        "ix_addresses_owner",
        "addresses",
        ["client_id", "owner_type", "owner_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_addresses_primary",
        "addresses",
        ["owner_type", "owner_id", "address_type"],
        unique=True,
        postgresql_where=sa.text("is_primary AND deleted_at IS NULL"),
    )

    # ------------------------------------------------------------------ passengers
    op.create_table(
        "passengers",
        *std_cols(),
        # NULLABLE on purpose: a guest may fly with no CRM contact record.
        sa.Column(
            "contact_id", UUID, sa.ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "status", pgenum("passenger_status"), nullable=False, server_default="active"
        ),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("middle_name", sa.Text(), nullable=True),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("preferred_name", sa.Text(), nullable=True),
        sa.Column("suffix", sa.Text(), nullable=True),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("nationality_code", sa.CHAR(2), nullable=True),
        sa.Column("gender_marker", sa.Text(), nullable=True),  # as printed on the travel doc
        sa.Column("weight_kg", sa.Numeric(5, 1), nullable=True),  # weight & balance
        sa.Column(
            "guardian_passenger_id",
            UUID,
            sa.ForeignKey("passengers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "dietary_restrictions",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "allergies",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "mobility_assistance", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("travels_with_pet", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("pet_details", JSONB(), nullable=True),
        sa.Column("preferences", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        # [enc] application-side envelope encryption; *_last4 for display
        # without decrypting (DATA_MODEL 1.2, and 5 "Encryption boundary").
        sa.Column("known_traveler_number", sa.LargeBinary(), nullable=True),
        sa.Column("ktn_last4", sa.Text(), nullable=True),
        sa.Column("redress_number", sa.LargeBinary(), nullable=True),
        sa.Column("emergency_contact_name", sa.Text(), nullable=True),
        sa.Column("emergency_contact_phone", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "search_tsv",
            pg.TSVECTOR(),
            sa.Computed(tsv("first_name", "last_name", "preferred_name"), persisted=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "guardian_passenger_id <> id", name="ck_passengers_no_self_guardian"
        ),
        sa.CheckConstraint(
            "weight_kg IS NULL OR weight_kg > 0", name="ck_passengers_weight_positive"
        ),
        comment="Flying identities. DATA_MODEL.md 3.2.",
    )
    std_indexes("passengers")
    op.create_index(
        "ix_passengers_contact",
        "passengers",
        ["client_id", "contact_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_passengers_name",
        "passengers",
        ["client_id", sa.text("lower(last_name)"), sa.text("lower(first_name)")],
    )
    op.create_index("ix_passengers_dob", "passengers", ["client_id", "date_of_birth"])
    op.create_index("ix_passengers_search", "passengers", ["search_tsv"], postgresql_using="gin")

    # ------------------------------------------------------------- account_holders
    op.create_table(
        "account_holders",
        *std_cols(),
        sa.Column("account_number", CITEXT(), nullable=False),  # 'ACC-00417'
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "account_type", pgenum("account_type"), nullable=False, server_default="individual"
        ),
        sa.Column("status", pgenum("account_status"), nullable=False, server_default="pending"),
        sa.Column(
            "primary_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "billing_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column(
            "payment_terms", pgenum("payment_terms"), nullable=False, server_default="prepaid"
        ),
        sa.Column("credit_limit_cents", money(), nullable=False, server_default="0"),
        # Materialized from invoices/payments; reconciled nightly.
        sa.Column("balance_cents", money(), nullable=False, server_default="0"),
        # Jet-card / block-hour wallet.
        sa.Column("prepaid_balance_cents", money(), nullable=False, server_default="0"),
        sa.Column("tax_id", sa.LargeBinary(), nullable=True),  # [enc]
        sa.Column("tax_id_last4", sa.Text(), nullable=True),
        sa.Column("tax_exempt", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "billing_address_id",
            UUID,
            sa.ForeignKey("addresses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("contract_signed_at", TS(), nullable=True),
        sa.Column("credit_reviewed_at", TS(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "credit_limit_cents >= 0", name="ck_account_holders_credit_limit_nonneg"
        ),
        comment="The commercial / billing entity -- who pays. DATA_MODEL.md 3.2.",
    )
    std_indexes("account_holders")
    op.create_index(
        "uq_account_holders_number",
        "account_holders",
        ["client_id", "account_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_account_holders_status",
        "account_holders",
        ["client_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_account_holders_contact", "account_holders", ["client_id", "primary_contact_id"]
    )
    op.create_index("ix_account_holders_owner", "account_holders", ["client_id", "owner_user_id"])
    # AR dashboards only ever want accounts that owe money.
    op.create_index(
        "ix_account_holders_balance",
        "account_holders",
        ["client_id", "balance_cents"],
        postgresql_where=sa.text("balance_cents > 0"),
    )

    # ---------------------------------------------------- account_holder_passengers
    # M:N -- who may fly on whose account. A guest flying on someone else's
    # account is one junction row, not a duplicate passenger.
    op.create_table(
        "account_holder_passengers",
        *std_cols(),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "passenger_id",
            UUID,
            sa.ForeignKey("passengers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship", pgenum("pax_relationship"), nullable=False, server_default="other"
        ),
        sa.Column(
            "is_authorized_booker", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("spend_limit_cents", money(), nullable=True),  # per-trip cap
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from",
            name="ck_ahp_valid_range",
        ),
        comment="Which passengers may fly on which account. DATA_MODEL.md 3.2.",
    )
    std_indexes("account_holder_passengers")
    op.create_index(
        "uq_ahp_account_passenger",
        "account_holder_passengers",
        ["account_holder_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_ahp_passenger", "account_holder_passengers", ["client_id", "passenger_id"])

    # ------------------------------------------------------------ travel_documents
    # Structured passport/visa data. The scanned image lives in `documents`.
    # Exclusive arc: exactly one of passenger_id / crew_member_id.
    op.create_table(
        "travel_documents",
        *std_cols(),
        sa.Column(
            "passenger_id",
            UUID,
            sa.ForeignKey("passengers.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # FK added in migration 007 (crew_members does not exist yet).
        sa.Column("crew_member_id", UUID, nullable=True),
        sa.Column("document_type", pgenum("travel_document_type"), nullable=False),
        sa.Column("number", sa.LargeBinary(), nullable=False),  # [enc]
        sa.Column("number_last4", sa.Text(), nullable=False),
        sa.Column("full_name_on_document", sa.Text(), nullable=False),
        sa.Column("issuing_country", sa.CHAR(2), nullable=False),
        sa.Column("nationality_code", sa.CHAR(2), nullable=True),
        sa.Column("place_of_birth", sa.Text(), nullable=True),
        sa.Column("issue_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        # FK added in migration 011 (documents does not exist yet).
        sa.Column("scan_document_id", UUID, nullable=True),
        sa.Column("verified_at", TS(), nullable=True),
        sa.Column(
            "verified_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint(
            "num_nonnulls(passenger_id, crew_member_id) = 1",
            name="ck_travel_documents_exclusive_arc",
        ),
        sa.CheckConstraint(
            "expiry_date IS NULL OR issue_date IS NULL OR expiry_date > issue_date",
            name="ck_travel_documents_date_order",
        ),
        comment="Passports, visas, crew licences. DATA_MODEL.md 3.2.",
    )
    std_indexes("travel_documents")
    op.create_index(
        "ix_travel_documents_passenger",
        "travel_documents",
        ["client_id", "passenger_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_travel_documents_crew",
        "travel_documents",
        ["client_id", "crew_member_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Drives the nightly expiry sweep that opens tasks (DATA_MODEL 5).
    op.create_index(
        "ix_travel_documents_expiry",
        "travel_documents",
        ["client_id", "expiry_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_travel_documents_primary",
        "travel_documents",
        ["passenger_id", "document_type"],
        unique=True,
        postgresql_where=sa.text("is_primary AND deleted_at IS NULL"),
    )

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml(
        "segments",
        "contacts",
        "contact_channels",
        "addresses",
        "passengers",
        "account_holders",
        "account_holder_passengers",
        "travel_documents",
    )


def downgrade() -> None:
    # Reverse FK dependency order.
    op.drop_table("travel_documents")
    op.drop_table("account_holder_passengers")
    op.drop_table("account_holders")
    op.drop_table("passengers")
    op.drop_table("addresses")
    op.drop_table("contact_channels")
    op.drop_table("contacts")
    op.drop_table("segments")
