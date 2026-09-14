"""Empty legs (DATA_MODEL.md 3.7)."""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Boolean, CHAR, CheckConstraint, Column, ForeignKey, Index, Integer, SmallInteger, Text, text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID
from sqlmodel import Field

from .base import BitluxBase, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import EmptyLegSource, EmptyLegStatus


class EmptyLeg(BitluxBase, TenantScopedMixin, table=True):
    """Operator repositioning flights offered for sale. DATA_MODEL.md 3.7."""
    __tablename__ = "empty_legs"
    __table_args__ = (
        *tenant_indexes("empty_legs"),
        Index("uq_empty_legs_external", "client_id", "source", "external_ref", unique=True, postgresql_where=text("external_ref IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_empty_legs_status_window", "client_id", "status", "earliest_departure_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_empty_legs_route", "client_id", "departure_airport_id", "arrival_airport_id", "earliest_departure_at", postgresql_where=text("status = 'available'")),
        Index("ix_empty_legs_operator", "client_id", "operator_id"),
        Index("ix_empty_legs_expiry", "client_id", "expires_at", postgresql_where=text("status = 'available'")),
        CheckConstraint("latest_departure_at >= earliest_departure_at", name="ck_empty_legs_window"),
        CheckConstraint("status <> 'booked' OR booked_trip_id IS NOT NULL", name="ck_empty_legs_booked_has_trip"),
        CheckConstraint("asking_price_cents >= 0", name="ck_empty_legs_price_nonneg"),
        CheckConstraint("floor_price_cents IS NULL OR floor_price_cents <= asking_price_cents", name="ck_empty_legs_floor_below_asking"),
        {"comment": "Operator repositioning flights offered for sale. DATA_MODEL.md 3.7."},
    )

    operator_id: uuid.UUID = Field(sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="CASCADE"), nullable=False))
    aircraft_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("aircraft_id", UUID(as_uuid=True), ForeignKey("aircraft.id", ondelete="SET NULL")))
    aircraft_model_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("aircraft_model_id", UUID(as_uuid=True), ForeignKey("aircraft_models.id", ondelete="SET NULL")))
    source_leg_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("source_leg_id", UUID(as_uuid=True), ForeignKey("legs.id", ondelete="SET NULL")))
    status: EmptyLegStatus = Field(default=EmptyLegStatus.DRAFT, sa_column=Column("status", pg_enum(EmptyLegStatus), nullable=False, server_default="draft"))
    source: EmptyLegSource = Field(default=EmptyLegSource.MANUAL, sa_column=Column("source", pg_enum(EmptyLegSource), nullable=False, server_default="manual"))
    departure_airport_id: uuid.UUID = Field(sa_column=Column("departure_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False))
    arrival_airport_id: uuid.UUID = Field(sa_column=Column("arrival_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="RESTRICT"), nullable=False))
    earliest_departure_at: datetime = Field(sa_column=Column("earliest_departure_at", TIMESTAMP(timezone=True), nullable=False))
    latest_departure_at: datetime = Field(sa_column=Column("latest_departure_at", TIMESTAMP(timezone=True), nullable=False))
    seats_available: Optional[int] = Field(default=None, sa_column=Column("seats_available", SmallInteger))
    asking_price_cents: int = Field(sa_column=Column("asking_price_cents", BigInteger, nullable=False))
    floor_price_cents: Optional[int] = Field(default=None, sa_column=Column("floor_price_cents", BigInteger))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    is_flexible_routing: bool = Field(default=False, sa_column=Column("is_flexible_routing", Boolean, nullable=False, server_default=text("false")))
    routing_radius_nm: Optional[int] = Field(default=None, sa_column=Column("routing_radius_nm", Integer))
    published_at: Optional[datetime] = Field(default=None, sa_column=Column("published_at", TIMESTAMP(timezone=True)))
    expires_at: Optional[datetime] = Field(default=None, sa_column=Column("expires_at", TIMESTAMP(timezone=True)))
    booked_trip_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("booked_trip_id", UUID(as_uuid=True), ForeignKey("trips.id", ondelete="SET NULL")))
    external_ref: Optional[str] = Field(default=None, sa_column=Column("external_ref", Text))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))
