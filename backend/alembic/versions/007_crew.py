"""007 - Crew members

DATA_MODEL.md 3.5.

Also closes the forward reference from migration 005:
``travel_documents.crew_member_id`` gets its FK here, now that ``crew_members``
exists. That column is one half of the exclusive arc enforced by
``ck_travel_documents_exclusive_arc`` -- a travel document belongs to exactly one
of a passenger or a crew member.

Forward FK attached in migration 011 (documents):
  * crew_members.photo_document_id

Revision ID: 007
Revises: 006
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
    pgenum,
    std_cols,
    std_indexes,
    tsv,
    UUID,
)

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "crew_members",
        *std_cols(),
        # NULL operator_id = in-house crew rather than an operator's employee.
        sa.Column(
            "operator_id", UUID, sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("primary_role", pgenum("crew_role"), nullable=False, server_default="pic"),
        sa.Column("status", pgenum("crew_status"), nullable=False, server_default="active"),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("nationality_code", sa.CHAR(2), nullable=True),
        sa.Column("email", CITEXT(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("license_number", sa.LargeBinary(), nullable=True),  # [enc]
        sa.Column("license_last4", sa.Text(), nullable=True),
        sa.Column("license_type", sa.Text(), nullable=True),  # 'ATP', 'CPL'
        sa.Column("license_country", sa.CHAR(2), nullable=True),
        sa.Column("medical_class", sa.Text(), nullable=True),  # 'Class 1'
        sa.Column("medical_expiry", sa.Date(), nullable=True),
        # ICAO type codes, e.g. {'GLF6','CL35'}. GIN-indexed for "who is current
        # on this type?" without a junction table.
        sa.Column(
            "type_ratings",
            pg.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("total_hours", sa.Integer(), nullable=True),
        # { "GLF6": 1200 } -- open-ended by type, not worth a table.
        sa.Column(
            "hours_on_type", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "base_airport_id",
            UUID,
            sa.ForeignKey("airports.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # FK added in migration 011.
        sa.Column("photo_document_id", UUID, nullable=True),
        sa.Column("last_recurrent_at", sa.Date(), nullable=True),
        sa.Column("next_recurrent_due", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "search_tsv",
            pg.TSVECTOR(),
            sa.Computed(tsv("first_name", "last_name", "email"), persisted=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "total_hours IS NULL OR total_hours >= 0", name="ck_crew_members_hours_nonneg"
        ),
        comment="Flight crew. DATA_MODEL.md 3.5.",
    )
    std_indexes("crew_members")
    op.create_index(
        "ix_crew_members_operator",
        "crew_members",
        ["client_id", "operator_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_crew_members_status",
        "crew_members",
        ["client_id", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_crew_members_type_ratings",
        "crew_members",
        ["type_ratings"],
        postgresql_using="gin",
    )
    # Currency sweeps -- only active crew can go out of currency.
    op.create_index(
        "ix_crew_members_medical_expiry",
        "crew_members",
        ["client_id", "medical_expiry"],
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_crew_members_recurrent_due",
        "crew_members",
        ["client_id", "next_recurrent_due"],
        postgresql_where=sa.text("status = 'active' AND deleted_at IS NULL"),
    )
    op.create_index("ix_crew_members_search", "crew_members", ["search_tsv"], postgresql_using="gin")

    # ------------------------------------ deferred FK from migration 005
    op.create_foreign_key(
        "fk_travel_documents_crew",
        "travel_documents",
        "crew_members",
        ["crew_member_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml("crew_members")


def downgrade() -> None:
    op.drop_constraint("fk_travel_documents_crew", "travel_documents", type_="foreignkey")
    op.drop_table("crew_members")
