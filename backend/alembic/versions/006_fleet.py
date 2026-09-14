"""006 - Fleet: operators, safety ratings, aircraft, operator history

DATA_MODEL.md 3.3.

Unlike the reference catalog in 003, ``operators`` and ``aircraft`` are
tenant-curated vendor records: ``client_id`` is NOT NULL. Two brokerages may
both deal with the same operator and will each hold their own row, with their
own status, commission and notes.

Forward FKs attached in migration 011 (documents):
  * operator_safety_ratings.report_document_id
  * aircraft_operator_assignments.management_agreement_document_id

Revision ID: 006
Revises: 005
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
    money,
    pgenum,
    std_cols,
    std_indexes,
    TS,
    tsv,
    UUID,
)

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------- operators
    op.create_table(
        "operators",
        *std_cols(),
        sa.Column("legal_name", sa.Text(), nullable=False),
        sa.Column("dba_name", sa.Text(), nullable=True),
        sa.Column("operator_code", CITEXT(), nullable=True),
        sa.Column(
            "status", pgenum("operator_status"), nullable=False, server_default="prospect"
        ),
        sa.Column("country_code", sa.CHAR(2), nullable=True),
        sa.Column("regulatory_part", pgenum("regulatory_part"), nullable=True),
        sa.Column("aoc_number", sa.Text(), nullable=True),
        sa.Column("aoc_expiry", sa.Date(), nullable=True),
        sa.Column("fleet_size", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column(
            "primary_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ops_email", CITEXT(), nullable=True),
        sa.Column("ops_phone", sa.Text(), nullable=True),
        sa.Column("ops_24h_phone", sa.Text(), nullable=True),
        sa.Column("accounts_email", CITEXT(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("insurance_expiry", sa.Date(), nullable=True),
        sa.Column("insurance_limit_cents", money(), nullable=True),
        sa.Column("w9_on_file", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("blocklist_reason", sa.Text(), nullable=True),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=True),  # 0.0750 = 7.5%
        sa.Column(
            "payment_terms", pgenum("payment_terms"), nullable=False, server_default="prepaid"
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "search_tsv",
            pg.TSVECTOR(),
            sa.Computed(tsv("legal_name", "dba_name", "operator_code"), persisted=True),
            nullable=True,
        ),
        # Blacklisting without a recorded reason is how institutional memory is
        # lost; the constraint forces the reason to be written down.
        sa.CheckConstraint(
            "status <> 'blacklisted' OR blocklist_reason IS NOT NULL",
            name="ck_operators_blocklist_reason",
        ),
        sa.CheckConstraint(
            "commission_rate IS NULL OR commission_rate BETWEEN 0 AND 1",
            name="ck_operators_commission_rate",
        ),
        comment="Charter operators / AOC holders. DATA_MODEL.md 3.3.",
    )
    std_indexes("operators")
    op.create_index(
        "uq_operators_code",
        "operators",
        ["client_id", "operator_code"],
        unique=True,
        postgresql_where=sa.text("operator_code IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "uq_operators_legal_name",
        "operators",
        ["client_id", sa.text("lower(legal_name)")],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_operators_status",
        "operators",
        ["client_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_operators_preferred",
        "operators",
        ["client_id"],
        postgresql_where=sa.text("is_preferred AND deleted_at IS NULL"),
    )
    # Both feed the nightly compliance sweep (DATA_MODEL 5).
    op.create_index(
        "ix_operators_insurance_expiry",
        "operators",
        ["client_id", "insurance_expiry"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_operators_aoc_expiry",
        "operators",
        ["client_id", "aoc_expiry"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_operators_search", "operators", ["search_tsv"], postgresql_using="gin")

    # ------------------------------------------------------ operator_safety_ratings
    op.create_table(
        "operator_safety_ratings",
        *std_cols(),
        sa.Column(
            "operator_id",
            UUID,
            sa.ForeignKey("operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("program", pgenum("safety_program"), nullable=False),
        sa.Column("rating_level", pgenum("safety_rating_level"), nullable=False),
        sa.Column("rating_label", sa.Text(), nullable=True),  # raw string from the auditor
        sa.Column("issued_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("audit_reference", sa.Text(), nullable=True),
        sa.Column("auditor_name", sa.Text(), nullable=True),
        sa.Column("scope_notes", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        # FK added in migration 011.
        sa.Column("report_document_id", UUID, nullable=True),
        sa.Column("verified_at", TS(), nullable=True),
        sa.Column(
            "verified_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "expiry_date IS NULL OR issued_date IS NULL OR expiry_date > issued_date",
            name="ck_safety_ratings_date_order",
        ),
        comment="ARGUS / Wyvern / IS-BAO ratings. DATA_MODEL.md 3.3.",
    )
    std_indexes("operator_safety_ratings")
    # Exactly one current rating per operator per program. Superseded ratings
    # stay as history with is_current = false.
    op.create_index(
        "uq_safety_ratings_current",
        "operator_safety_ratings",
        ["operator_id", "program"],
        unique=True,
        postgresql_where=sa.text("is_current AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_safety_ratings_operator",
        "operator_safety_ratings",
        ["client_id", "operator_id", "program"],
    )
    op.create_index(
        "ix_safety_ratings_expiry",
        "operator_safety_ratings",
        ["client_id", "expiry_date"],
        postgresql_where=sa.text("is_current AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_safety_ratings_level", "operator_safety_ratings", ["client_id", "rating_level"]
    )

    # -------------------------------------------------------------------- aircraft
    op.create_table(
        "aircraft",
        *std_cols(),
        sa.Column("tail_number", CITEXT(), nullable=False),  # 'N650BX'
        sa.Column("serial_number", sa.Text(), nullable=True),
        sa.Column(
            "aircraft_model_id",
            UUID,
            sa.ForeignKey("aircraft_models.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # Current operator. The full history lives in
        # aircraft_operator_assignments below.
        sa.Column(
            "operator_id", UUID, sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "owner_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", pgenum("aircraft_status"), nullable=False, server_default="active"
        ),
        sa.Column("year_of_manufacture", sa.SmallInteger(), nullable=True),
        sa.Column("registration_country", sa.CHAR(2), nullable=True),
        sa.Column(
            "home_base_airport_id",
            UUID,
            sa.ForeignKey("airports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # Overrides the model default when this tail is configured differently.
        sa.Column("max_passengers", sa.SmallInteger(), nullable=True),
        sa.Column("configured_seats", sa.SmallInteger(), nullable=True),
        sa.Column("divans", sa.SmallInteger(), nullable=True),
        sa.Column("berths", sa.SmallInteger(), nullable=True),
        sa.Column("interior_refurb_year", sa.SmallInteger(), nullable=True),
        sa.Column("exterior_refurb_year", sa.SmallInteger(), nullable=True),
        sa.Column("wifi_provider", sa.Text(), nullable=True),  # 'Starlink', 'Gogo Avance'
        sa.Column("amenities", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("pets_allowed", sa.Boolean(), nullable=True),
        sa.Column("smoking_allowed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("lavatory_type", sa.Text(), nullable=True),
        sa.Column("cargo_capacity_cuft", sa.Integer(), nullable=True),
        sa.Column("hourly_rate_cents", money(), nullable=True),
        sa.Column(
            "is_available_for_charter", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column("last_verified_at", TS(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "search_tsv",
            pg.TSVECTOR(),
            sa.Computed(tsv("tail_number", "serial_number"), persisted=True),
            nullable=True,
        ),
        comment="Physical tail numbers. DATA_MODEL.md 3.3.",
    )
    std_indexes("aircraft")
    op.create_index(
        "uq_aircraft_tail",
        "aircraft",
        ["client_id", "tail_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_aircraft_operator",
        "aircraft",
        ["client_id", "operator_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_aircraft_model",
        "aircraft",
        ["client_id", "aircraft_model_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_aircraft_availability",
        "aircraft",
        ["client_id", "status", "is_available_for_charter"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_aircraft_home_base", "aircraft", ["client_id", "home_base_airport_id"])
    op.create_index("ix_aircraft_search", "aircraft", ["search_tsv"], postgresql_using="gin")

    # ------------------------------------------- aircraft_operator_assignments
    # Tails move between operators; keep the history so a past trip can still be
    # attributed to whoever actually held the certificate that day.
    op.create_table(
        "aircraft_operator_assignments",
        *std_cols(),
        sa.Column(
            "aircraft_id", UUID, sa.ForeignKey("aircraft.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "operator_id",
            UUID,
            sa.ForeignKey("operators.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),  # NULL = current
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
        # FK added in migration 011.
        sa.Column("management_agreement_document_id", UUID, nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "effective_to IS NULL OR effective_to > effective_from",
            name="ck_aoa_date_order",
        ),
        comment="Aircraft <-> operator tenure history. DATA_MODEL.md 3.3.",
    )
    std_indexes("aircraft_operator_assignments")
    # The real guarantee: one tail cannot be on two certificates at once.
    # '=' on uuid inside a GiST index is what btree_gist (migration 001) provides.
    op.execute(
        """
        ALTER TABLE aircraft_operator_assignments
          ADD CONSTRAINT ex_aoa_no_overlap
          EXCLUDE USING GIST (
              aircraft_id WITH =,
              daterange(effective_from, effective_to, '[)') WITH &&
          ) WHERE (deleted_at IS NULL)
        """
    )
    op.create_index(
        "uq_aoa_current",
        "aircraft_operator_assignments",
        ["aircraft_id"],
        unique=True,
        postgresql_where=sa.text("is_current AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_aoa_aircraft",
        "aircraft_operator_assignments",
        ["client_id", "aircraft_id", sa.text("effective_from DESC")],
    )
    op.create_index("ix_aoa_operator", "aircraft_operator_assignments", ["client_id", "operator_id"])

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml(
        "operators",
        "operator_safety_ratings",
        "aircraft",
        "aircraft_operator_assignments",
    )


def downgrade() -> None:
    op.drop_table("aircraft_operator_assignments")
    op.drop_table("aircraft")
    op.drop_table("operator_safety_ratings")
    op.drop_table("operators")
