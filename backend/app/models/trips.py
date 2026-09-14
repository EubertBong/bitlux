"""Trips -> Legs -> Manifests -> Crew (DATA_MODEL.md 3.6)."""

import uuid
from datetime import date, datetime
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CHAR, CheckConstraint, Column, Computed, Date, ForeignKey, Index, Integer, SmallInteger, Text, text, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import CrewRole, LeadSource, LegPurpose, LegStatus, TripStatus, TripType

if TYPE_CHECKING:
    from .commerce import Booking, Quote
    from .crew import CrewMember
    from .crm import AccountHolder, Passenger
    from .fleet import Aircraft


class Trip(BitluxBase, TenantScopedMixin, table=True):
    """A customer journey, one or more legs. DATA_MODEL.md 3.6."""
    __tablename__ = "trips"
    __table_args__ = (
        *tenant_indexes("trips"),
        Index("uq_trips_number", "client_id", "trip_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_trips_status_departure", "client_id", "status", "departure_date", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_trips_account", "client_id", "account_holder_id", text("departure_date DESC")),
        Index("ix_trips_owner", "client_id", "owner_user_id", "status"),
        Index("ix_trips_live_departure", "client_id", "departure_date", postgresql_where=text("status IN ('confirmed','in_progress')")),
        CheckConstraint("status <> 'cancelled' OR cancelled_at IS NOT NULL", name="ck_trips_cancelled_at"),
        CheckConstraint("return_date IS NULL OR departure_date IS NULL OR return_date >= departure_date", name="ck_trips_date_order"),
        {"comment": "A customer journey, one or more legs. DATA_MODEL.md 3.6."},
    )

    trip_number: str = Field(sa_column=Column("trip_number", CITEXT, nullable=False))
    trip_type: TripType = Field(default=TripType.CHARTER, sa_column=Column("trip_type", pg_enum(TripType), nullable=False, server_default="charter"))
    status: TripStatus = Field(default=TripStatus.DRAFT, sa_column=Column("status", pg_enum(TripStatus), nullable=False, server_default="draft"))
    account_holder_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="RESTRICT")))
    primary_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("primary_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    lead_passenger_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("lead_passenger_id", UUID(as_uuid=True), ForeignKey("passengers.id", ondelete="SET NULL")))
    owner_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("owner_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    ops_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("ops_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    accepted_quote_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("accepted_quote_id", UUID(as_uuid=True), ForeignKey("quotes.id", ondelete="SET NULL", deferrable=True, initially="DEFERRED", name="fk_trips_accepted_quote")))
    booking_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("booking_id", UUID(as_uuid=True), ForeignKey("bookings.id", ondelete="SET NULL", deferrable=True, initially="DEFERRED", name="fk_trips_booking")))
    source_empty_leg_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("source_empty_leg_id", UUID(as_uuid=True), ForeignKey("empty_legs.id", ondelete="SET NULL", name="fk_trips_source_empty_leg")))
    source: LeadSource = Field(default=LeadSource.OTHER, sa_column=Column("source", pg_enum(LeadSource), nullable=False, server_default="other"))
    pax_count: int = Field(default=0, sa_column=Column("pax_count", SmallInteger, nullable=False, server_default="0"))
    leg_count: int = Field(default=0, sa_column=Column("leg_count", SmallInteger, nullable=False, server_default="0"))
    departure_date: Optional[date] = Field(default=None, sa_column=Column("departure_date", Date))
    return_date: Optional[date] = Field(default=None, sa_column=Column("return_date", Date))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    total_sell_cents: int = Field(default=0, sa_column=Column("total_sell_cents", BigInteger, nullable=False, server_default="0"))
    total_cost_cents: int = Field(default=0, sa_column=Column("total_cost_cents", BigInteger, nullable=False, server_default="0"))
    margin_cents: Optional[int] = Field(default=None, sa_column=Column("margin_cents", BigInteger, Computed("total_sell_cents - total_cost_cents", persisted=True)))
    special_requests: Optional[str] = Field(default=None, sa_column=Column("special_requests", Text))
    internal_notes: Optional[str] = Field(default=None, sa_column=Column("internal_notes", Text))
    cancelled_at: Optional[datetime] = Field(default=None, sa_column=Column("cancelled_at", TIMESTAMP(timezone=True)))
    cancellation_reason: Optional[str] = Field(default=None, sa_column=Column("cancellation_reason", Text))

    account_holder: Optional["AccountHolder"] = Relationship(back_populates="trips")
    legs: list["Leg"] = Relationship(back_populates="trip", cascade_delete=True, sa_relationship_kwargs={"order_by": "Leg.leg_number"})
    quotes: list["Quote"] = Relationship(back_populates="trip", sa_relationship_kwargs={"foreign_keys": "[Quote.trip_id]"})
    bookings: list["Booking"] = Relationship(back_populates="trip", sa_relationship_kwargs={"foreign_keys": "[Booking.trip_id]"})


class Leg(BitluxBase, TenantScopedMixin, table=True):
    """A single flight sector. DATA_MODEL.md 3.6."""
    __tablename__ = "legs"
    __table_args__ = (
        *tenant_indexes("legs"),
        Index("uq_legs_trip_number", "trip_id", "leg_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_legs_departure_at", "client_id", "scheduled_departure_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_legs_aircraft_schedule", "client_id", "aircraft_id", "scheduled_departure_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_legs_departure_airport", "client_id", "departure_airport_id", "scheduled_departure_at"),
        Index("ix_legs_arrival_airport", "client_id", "arrival_airport_id", "scheduled_arrival_at"),
        Index("ix_legs_operator_schedule", "client_id", "operator_id", "scheduled_departure_at"),
        Index("ix_legs_active_status", "client_id", "status", postgresql_where=text("status IN ('scheduled','released','departed','enroute')")),
        CheckConstraint("scheduled_arrival_at > scheduled_departure_at", name="ck_legs_schedule_order"),
        CheckConstraint("departure_airport_id <> arrival_airport_id OR purpose = 'training'", name="ck_legs_distinct_airports"),
        CheckConstraint("leg_number > 0", name="ck_legs_number_positive"),
        {"comment": "A single flight sector. DATA_MODEL.md 3.6."},
    )

    trip_id: uuid.UUID = Field(sa_column=Column("trip_id", UUID(as_uuid=True), ForeignKey("trips.id", ondelete="CASCADE"), nullable=False))
    leg_number: int = Field(sa_column=Column("leg_number", SmallInteger, nullable=False))
    status: LegStatus = Field(default=LegStatus.SCHEDULED, sa_column=Column("status", pg_enum(LegStatus), nullable=False, server_default="scheduled"))
    purpose: LegPurpose = Field(default=LegPurpose.REVENUE, sa_column=Column("purpose", pg_enum(LegPurpose), nullable=False, server_default="revenue"))
    departure_airport_id: uuid.UUID = Field(sa_column=Column("departure_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False))
    arrival_airport_id: uuid.UUID = Field(sa_column=Column("arrival_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False))
    departure_fbo_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("departure_fbo_id", UUID(as_uuid=True), ForeignKey("fbos.id", ondelete="SET NULL")))
    arrival_fbo_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("arrival_fbo_id", UUID(as_uuid=True), ForeignKey("fbos.id", ondelete="SET NULL")))
    scheduled_departure_at: datetime = Field(sa_column=Column("scheduled_departure_at", TIMESTAMP(timezone=True), nullable=False))
    scheduled_arrival_at: datetime = Field(sa_column=Column("scheduled_arrival_at", TIMESTAMP(timezone=True), nullable=False))
    departure_timezone: str = Field(sa_column=Column("departure_timezone", Text, nullable=False))
    arrival_timezone: str = Field(sa_column=Column("arrival_timezone", Text, nullable=False))
    actual_departure_at: Optional[datetime] = Field(default=None, sa_column=Column("actual_departure_at", TIMESTAMP(timezone=True)))
    actual_arrival_at: Optional[datetime] = Field(default=None, sa_column=Column("actual_arrival_at", TIMESTAMP(timezone=True)))
    block_time_minutes: Optional[int] = Field(default=None, sa_column=Column("block_time_minutes", Integer))
    flight_time_minutes: Optional[int] = Field(default=None, sa_column=Column("flight_time_minutes", Integer))
    distance_nm: Optional[int] = Field(default=None, sa_column=Column("distance_nm", Integer))
    aircraft_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("aircraft_id", UUID(as_uuid=True), ForeignKey("aircraft.id", ondelete="SET NULL")))
    operator_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="SET NULL")))
    flight_number: Optional[str] = Field(default=None, sa_column=Column("flight_number", Text))
    pax_count: int = Field(default=0, sa_column=Column("pax_count", SmallInteger, nullable=False, server_default="0"))
    baggage_notes: Optional[str] = Field(default=None, sa_column=Column("baggage_notes", Text))
    catering_notes: Optional[str] = Field(default=None, sa_column=Column("catering_notes", Text))
    ground_transport: dict[str, Any] = Field(default_factory=dict, sa_column=Column("ground_transport", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    customs_required: bool = Field(default=False, sa_column=Column("customs_required", Boolean, nullable=False, server_default=text("false")))
    is_tech_stop: bool = Field(default=False, sa_column=Column("is_tech_stop", Boolean, nullable=False, server_default=text("false")))
    cost_cents: int = Field(default=0, sa_column=Column("cost_cents", BigInteger, nullable=False, server_default="0"))
    sell_cents: int = Field(default=0, sa_column=Column("sell_cents", BigInteger, nullable=False, server_default="0"))
    delay_minutes: Optional[int] = Field(default=None, sa_column=Column("delay_minutes", Integer))
    delay_reason: Optional[str] = Field(default=None, sa_column=Column("delay_reason", Text))

    aircraft: Optional["Aircraft"] = Relationship(back_populates="legs")
    trip: Optional["Trip"] = Relationship(back_populates="legs")
    manifest: list["LegPassenger"] = Relationship(back_populates="leg", cascade_delete=True)
    crew: list["LegCrew"] = Relationship(back_populates="leg", cascade_delete=True)


class LegPassenger(BitluxBase, TenantScopedMixin, table=True):
    """Passenger manifest per leg. DATA_MODEL.md 3.6."""
    __tablename__ = "leg_passengers"
    __table_args__ = (
        *tenant_indexes("leg_passengers"),
        Index("uq_leg_passengers_pair", "leg_id", "passenger_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_leg_passengers_lead", "leg_id", unique=True, postgresql_where=text("is_lead_passenger AND deleted_at IS NULL")),
        Index("ix_leg_passengers_passenger", "client_id", "passenger_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_leg_passengers_leg", "client_id", "leg_id"),
        {"comment": "Passenger manifest per leg. DATA_MODEL.md 3.6."},
    )

    leg_id: uuid.UUID = Field(sa_column=Column("leg_id", UUID(as_uuid=True), ForeignKey("legs.id", ondelete="CASCADE"), nullable=False))
    passenger_id: uuid.UUID = Field(sa_column=Column("passenger_id", UUID(as_uuid=True), ForeignKey("passengers.id", ondelete="RESTRICT"), nullable=False))
    is_lead_passenger: bool = Field(default=False, sa_column=Column("is_lead_passenger", Boolean, nullable=False, server_default=text("false")))
    seat_assignment: Optional[str] = Field(default=None, sa_column=Column("seat_assignment", Text))
    travel_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("travel_document_id", UUID(as_uuid=True), ForeignKey("travel_documents.id", ondelete="SET NULL")))
    catering_selection: dict[str, Any] = Field(default_factory=dict, sa_column=Column("catering_selection", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    special_requests: Optional[str] = Field(default=None, sa_column=Column("special_requests", Text))
    checked_in_at: Optional[datetime] = Field(default=None, sa_column=Column("checked_in_at", TIMESTAMP(timezone=True)))
    boarded_at: Optional[datetime] = Field(default=None, sa_column=Column("boarded_at", TIMESTAMP(timezone=True)))
    is_no_show: bool = Field(default=False, sa_column=Column("is_no_show", Boolean, nullable=False, server_default=text("false")))
    manifest_submitted_at: Optional[datetime] = Field(default=None, sa_column=Column("manifest_submitted_at", TIMESTAMP(timezone=True)))

    leg: Optional["Leg"] = Relationship(back_populates="manifest")
    passenger: Optional["Passenger"] = Relationship()


class LegCrew(BitluxBase, TenantScopedMixin, table=True):
    """Crew assignment per leg. DATA_MODEL.md 3.6."""
    __tablename__ = "leg_crew"
    __table_args__ = (
        *tenant_indexes("leg_crew"),
        Index("uq_leg_crew_pair", "leg_id", "crew_member_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_leg_crew_pic", "leg_id", unique=True, postgresql_where=text("crew_role = 'pic' AND deleted_at IS NULL")),
        Index("ix_leg_crew_duty", "client_id", "crew_member_id", "duty_start_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_leg_crew_leg", "client_id", "leg_id"),
        CheckConstraint("duty_end_at IS NULL OR duty_start_at IS NULL OR duty_end_at > duty_start_at", name="ck_leg_crew_duty_order"),
        {"comment": "Crew assignment per leg. DATA_MODEL.md 3.6."},
    )

    leg_id: uuid.UUID = Field(sa_column=Column("leg_id", UUID(as_uuid=True), ForeignKey("legs.id", ondelete="CASCADE"), nullable=False))
    crew_member_id: uuid.UUID = Field(sa_column=Column("crew_member_id", UUID(as_uuid=True), ForeignKey("crew_members.id", ondelete="RESTRICT"), nullable=False))
    crew_role: CrewRole = Field(sa_column=Column("crew_role", pg_enum(CrewRole), nullable=False))
    duty_start_at: Optional[datetime] = Field(default=None, sa_column=Column("duty_start_at", TIMESTAMP(timezone=True)))
    duty_end_at: Optional[datetime] = Field(default=None, sa_column=Column("duty_end_at", TIMESTAMP(timezone=True)))
    hotel_details: dict[str, Any] = Field(default_factory=dict, sa_column=Column("hotel_details", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    leg: Optional["Leg"] = Relationship(back_populates="crew")
    crew_member: Optional["CrewMember"] = Relationship()
