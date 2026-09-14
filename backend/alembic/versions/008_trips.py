"""008 - Trips -> Legs -> Manifests -> Crew

DATA_MODEL.md 3.6.

``legs`` is the operational heart of the system and carries the two indexes that
do real work at 3am:

  * (client_id, aircraft_id, scheduled_departure_at) -- double-booked tails
  * leg_crew (client_id, crew_member_id, duty_start_at) -- crew duty overlap

Circular FK note (DATA_MODEL 3.6): trips <-> quotes <-> bookings reference each
other. ``trips.accepted_quote_id`` and ``trips.booking_id`` are created bare here
and attached in migration 010 as DEFERRABLE INITIALLY DEFERRED, so a trip, its
quote and its booking can be written in a single transaction in any order.
``quotes.trip_id`` and ``bookings.trip_id`` are the non-deferred, authoritative
edges.

Forward FK attached in migration 009:
  * trips.source_empty_leg_id -> empty_legs

Revision ID: 008
Revises: 007
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import CITEXT, JSONB, TS, UUID, money, pgenum, std_cols, std_indexes

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ----------------------------------------------------------------------- trips
    op.create_table(
        "trips",
        *std_cols(),
        sa.Column("trip_number", CITEXT(), nullable=False),  # 'BLX-2026-00147'
        sa.Column("trip_type", pgenum("trip_type"), nullable=False, server_default="charter"),
        sa.Column("status", pgenum("trip_status"), nullable=False, server_default="draft"),
        # NULL until the trip is attached to a paying account.
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "primary_contact_id",
            UUID,
            sa.ForeignKey("contacts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lead_passenger_id",
            UUID,
            sa.ForeignKey("passengers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "owner_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),  # broker
        sa.Column(
            "ops_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),  # trip support
        # FKs added in migration 010, DEFERRABLE (see module docstring).
        sa.Column("accepted_quote_id", UUID, nullable=True),
        sa.Column("booking_id", UUID, nullable=True),
        # FK added in migration 009.
        sa.Column("source_empty_leg_id", UUID, nullable=True),
        sa.Column("source", pgenum("lead_source"), nullable=False, server_default="other"),
        sa.Column("pax_count", sa.SmallInteger(), nullable=False, server_default="0"),
        # Materialized from legs so list views do not aggregate on every render.
        sa.Column("leg_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("departure_date", sa.Date(), nullable=True),  # first leg
        sa.Column("return_date", sa.Date(), nullable=True),  # last leg
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("total_sell_cents", money(), nullable=False, server_default="0"),
        sa.Column("total_cost_cents", money(), nullable=False, server_default="0"),
        sa.Column(
            "margin_cents",
            money(),
            sa.Computed("total_sell_cents - total_cost_cents", persisted=True),
            nullable=True,
        ),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("internal_notes", sa.Text(), nullable=True),
        sa.Column("cancelled_at", TS(), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancelled_at IS NOT NULL",
            name="ck_trips_cancelled_at",
        ),
        sa.CheckConstraint(
            "return_date IS NULL OR departure_date IS NULL OR return_date >= departure_date",
            name="ck_trips_date_order",
        ),
        comment="A customer journey, one or more legs. DATA_MODEL.md 3.6.",
    )
    std_indexes("trips")
    op.create_index(
        "uq_trips_number",
        "trips",
        ["client_id", "trip_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_trips_status_departure",
        "trips",
        ["client_id", "status", "departure_date"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_trips_account",
        "trips",
        ["client_id", "account_holder_id", sa.text("departure_date DESC")],
    )
    op.create_index("ix_trips_owner", "trips", ["client_id", "owner_user_id", "status"])
    # The ops board: everything live, ordered by departure.
    op.create_index(
        "ix_trips_live_departure",
        "trips",
        ["client_id", "departure_date"],
        postgresql_where=sa.text("status IN ('confirmed','in_progress')"),
    )

    # ------------------------------------------------------------------------ legs
    op.create_table(
        "legs",
        *std_cols(),
        sa.Column("trip_id", UUID, sa.ForeignKey("trips.id", ondelete="CASCADE"), nullable=False),
        sa.Column("leg_number", sa.SmallInteger(), nullable=False),  # 1-based within trip
        sa.Column("status", pgenum("leg_status"), nullable=False, server_default="scheduled"),
        sa.Column("purpose", pgenum("leg_purpose"), nullable=False, server_default="revenue"),
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
        sa.Column(
            "departure_fbo_id", UUID, sa.ForeignKey("fbos.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "arrival_fbo_id", UUID, sa.ForeignKey("fbos.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("scheduled_departure_at", TS(), nullable=False),
        sa.Column("scheduled_arrival_at", TS(), nullable=False),
        # IANA zone snapshotted from the airport at creation, so the local
        # wall-clock a customer was told stays reconstructable even if the
        # airport record or the tz database later changes.
        sa.Column("departure_timezone", sa.Text(), nullable=False),
        sa.Column("arrival_timezone", sa.Text(), nullable=False),
        sa.Column("actual_departure_at", TS(), nullable=True),
        sa.Column("actual_arrival_at", TS(), nullable=True),
        sa.Column("block_time_minutes", sa.Integer(), nullable=True),
        sa.Column("flight_time_minutes", sa.Integer(), nullable=True),
        # Great-circle, computed in the application (DATA_MODEL 1.6) -- never
        # derived from the planar `airports.location` point.
        sa.Column("distance_nm", sa.Integer(), nullable=True),
        sa.Column(
            "aircraft_id", UUID, sa.ForeignKey("aircraft.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "operator_id", UUID, sa.ForeignKey("operators.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column("flight_number", sa.Text(), nullable=True),
        sa.Column("pax_count", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("baggage_notes", sa.Text(), nullable=True),
        sa.Column("catering_notes", sa.Text(), nullable=True),
        sa.Column(
            "ground_transport", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("customs_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_tech_stop", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cost_cents", money(), nullable=False, server_default="0"),
        sa.Column("sell_cents", money(), nullable=False, server_default="0"),
        sa.Column("delay_minutes", sa.Integer(), nullable=True),
        sa.Column("delay_reason", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "scheduled_arrival_at > scheduled_departure_at", name="ck_legs_schedule_order"
        ),
        # A circular route is only meaningful for training.
        sa.CheckConstraint(
            "departure_airport_id <> arrival_airport_id OR purpose = 'training'",
            name="ck_legs_distinct_airports",
        ),
        sa.CheckConstraint("leg_number > 0", name="ck_legs_number_positive"),
        comment="A single flight sector. DATA_MODEL.md 3.6.",
    )
    std_indexes("legs")
    op.create_index(
        "uq_legs_trip_number",
        "legs",
        ["trip_id", "leg_number"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_legs_departure_at",
        "legs",
        ["client_id", "scheduled_departure_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Tail double-booking detection.
    op.create_index(
        "ix_legs_aircraft_schedule",
        "legs",
        ["client_id", "aircraft_id", "scheduled_departure_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_legs_departure_airport",
        "legs",
        ["client_id", "departure_airport_id", "scheduled_departure_at"],
    )
    op.create_index(
        "ix_legs_arrival_airport",
        "legs",
        ["client_id", "arrival_airport_id", "scheduled_arrival_at"],
    )
    op.create_index(
        "ix_legs_operator_schedule",
        "legs",
        ["client_id", "operator_id", "scheduled_departure_at"],
    )
    op.create_index(
        "ix_legs_active_status",
        "legs",
        ["client_id", "status"],
        postgresql_where=sa.text(
            "status IN ('scheduled','released','departed','enroute')"
        ),
    )

    # -------------------------------------------------------------- leg_passengers
    # THE MANIFEST.
    op.create_table(
        "leg_passengers",
        *std_cols(),
        sa.Column("leg_id", UUID, sa.ForeignKey("legs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "passenger_id",
            UUID,
            sa.ForeignKey("passengers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("is_lead_passenger", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("seat_assignment", sa.Text(), nullable=True),
        # Which document this passenger actually travelled on -- the manifest
        # record has to survive the passenger later renewing their passport.
        sa.Column(
            "travel_document_id",
            UUID,
            sa.ForeignKey("travel_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "catering_selection", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("checked_in_at", TS(), nullable=True),
        sa.Column("boarded_at", TS(), nullable=True),
        sa.Column("is_no_show", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("manifest_submitted_at", TS(), nullable=True),  # APIS / eAPIS filing
        comment="Passenger manifest per leg. DATA_MODEL.md 3.6.",
    )
    std_indexes("leg_passengers")
    op.create_index(
        "uq_leg_passengers_pair",
        "leg_passengers",
        ["leg_id", "passenger_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_leg_passengers_lead",
        "leg_passengers",
        ["leg_id"],
        unique=True,
        postgresql_where=sa.text("is_lead_passenger AND deleted_at IS NULL"),
    )
    # "where has this passenger flown?"
    op.create_index(
        "ix_leg_passengers_passenger",
        "leg_passengers",
        ["client_id", "passenger_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_leg_passengers_leg", "leg_passengers", ["client_id", "leg_id"])

    # -------------------------------------------------------------------- leg_crew
    op.create_table(
        "leg_crew",
        *std_cols(),
        sa.Column("leg_id", UUID, sa.ForeignKey("legs.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "crew_member_id",
            UUID,
            sa.ForeignKey("crew_members.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("crew_role", pgenum("crew_role"), nullable=False),
        sa.Column("duty_start_at", TS(), nullable=True),
        sa.Column("duty_end_at", TS(), nullable=True),
        sa.Column(
            "hotel_details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "duty_end_at IS NULL OR duty_start_at IS NULL OR duty_end_at > duty_start_at",
            name="ck_leg_crew_duty_order",
        ),
        comment="Crew assignment per leg. DATA_MODEL.md 3.6.",
    )
    std_indexes("leg_crew")
    op.create_index(
        "uq_leg_crew_pair",
        "leg_crew",
        ["leg_id", "crew_member_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Exactly one pilot in command per leg.
    op.create_index(
        "uq_leg_crew_pic",
        "leg_crew",
        ["leg_id"],
        unique=True,
        postgresql_where=sa.text("crew_role = 'pic' AND deleted_at IS NULL"),
    )
    # Duty-time overlap detection.
    op.create_index(
        "ix_leg_crew_duty",
        "leg_crew",
        ["client_id", "crew_member_id", "duty_start_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_leg_crew_leg", "leg_crew", ["client_id", "leg_id"])


def downgrade() -> None:
    op.drop_table("leg_crew")
    op.drop_table("leg_passengers")
    op.drop_table("legs")
    op.drop_table("trips")
