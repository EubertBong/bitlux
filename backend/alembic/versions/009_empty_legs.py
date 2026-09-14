"""009 - Empty legs

DATA_MODEL.md 3.7.

An empty leg is a positioning flight an operator is willing to sell. It has a
departure *window* rather than a departure time, and often flexible endpoints,
which is why it cannot simply be modelled as a discounted ``leg``.

Also closes the forward reference from migration 008:
``trips.source_empty_leg_id`` -- the trip that was booked off this offer. Note
the two tables point at each other (``empty_legs.booked_trip_id`` /
``trips.source_empty_leg_id``); both are ON DELETE SET NULL and neither is
mandatory, so no deferral is needed.

Revision ID: 009
Revises: 008
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import (
    grant_app_dml,
    money,
    pgenum,
    std_cols,
    std_indexes,
    TS,
    UUID,
)

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "empty_legs",
        *std_cols(),
        sa.Column(
            "operator_id",
            UUID,
            sa.ForeignKey("operators.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "aircraft_id", UUID, sa.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True
        ),
        # Feeds often name only a type, not a tail.
        sa.Column(
            "aircraft_model_id",
            UUID,
            sa.ForeignKey("aircraft_models.id", ondelete="SET NULL"),
            nullable=True,
        ),
        # The positioning leg that created the offer, when we know it.
        sa.Column(
            "source_leg_id", UUID, sa.ForeignKey("legs.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "status", pgenum("empty_leg_status"), nullable=False, server_default="draft"
        ),
        sa.Column(
            "source", pgenum("empty_leg_source"), nullable=False, server_default="manual"
        ),
        sa.Column(
            "departure_airport_id",
            UUID,
            sa.ForeignKey("airports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "arrival_airport_id",
            UUID,
            sa.ForeignKey("airports.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        # The flex window, not a departure time.
        sa.Column("earliest_departure_at", TS(), nullable=False),
        sa.Column("latest_departure_at", TS(), nullable=False),
        sa.Column("seats_available", sa.SmallInteger(), nullable=True),
        sa.Column("asking_price_cents", money(), nullable=False),
        # Internal walk-away price -- never exposed to a customer.
        sa.Column("floor_price_cents", money(), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column(
            "is_flexible_routing", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
        sa.Column("routing_radius_nm", sa.Integer(), nullable=True),
        sa.Column("published_at", TS(), nullable=True),
        sa.Column("expires_at", TS(), nullable=True),
        sa.Column(
            "booked_trip_id", UUID, sa.ForeignKey("trips.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("external_ref", sa.Text(), nullable=True),  # Avinode / operator feed id
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "latest_departure_at >= earliest_departure_at", name="ck_empty_legs_window"
        ),
        sa.CheckConstraint(
            "status <> 'booked' OR booked_trip_id IS NOT NULL",
            name="ck_empty_legs_booked_has_trip",
        ),
        sa.CheckConstraint("asking_price_cents >= 0", name="ck_empty_legs_price_nonneg"),
        sa.CheckConstraint(
            "floor_price_cents IS NULL OR floor_price_cents <= asking_price_cents",
            name="ck_empty_legs_floor_below_asking",
        ),
        comment="Operator repositioning flights offered for sale. DATA_MODEL.md 3.7.",
    )
    std_indexes("empty_legs")
    # Ingested feeds re-send the same offer; dedupe on the upstream id.
    op.create_index(
        "uq_empty_legs_external",
        "empty_legs",
        ["client_id", "source", "external_ref"],
        unique=True,
        postgresql_where=sa.text("external_ref IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "ix_empty_legs_status_window",
        "empty_legs",
        ["client_id", "status", "earliest_departure_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # The customer-facing search: route + date, only what is actually sellable.
    op.create_index(
        "ix_empty_legs_route",
        "empty_legs",
        [
            "client_id",
            "departure_airport_id",
            "arrival_airport_id",
            "earliest_departure_at",
        ],
        postgresql_where=sa.text("status = 'available'"),
    )
    op.create_index("ix_empty_legs_operator", "empty_legs", ["client_id", "operator_id"])
    op.create_index(
        "ix_empty_legs_expiry",
        "empty_legs",
        ["client_id", "expires_at"],
        postgresql_where=sa.text("status = 'available'"),
    )

    # ------------------------------------ deferred FK from migration 008
    op.create_foreign_key(
        "fk_trips_source_empty_leg",
        "trips",
        "empty_legs",
        ["source_empty_leg_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # --- application role: full DML on these ordinary tenant tables -------------
    # Explicit per table so every UPDATE/DELETE grant is a greppable line
    # (DATA_MODEL 1.7). audit_logs in 012 pointedly does not get this.
    grant_app_dml("empty_legs")


def downgrade() -> None:
    op.drop_constraint("fk_trips_source_empty_leg", "trips", type_="foreignkey")
    op.drop_table("empty_legs")
