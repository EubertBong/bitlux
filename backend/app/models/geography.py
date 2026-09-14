"""Geography: airports and FBOs, shared reference catalog (DATA_MODEL.md 3.4)."""

import uuid
from decimal import Decimal
from typing import Any, Optional

from sqlalchemy import Boolean, CHAR, CheckConstraint, Column, Computed, ForeignKey, Index, Integer, Numeric, Text, text
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, POINT, SharedCatalogMixin, tenant_indexes


class Airport(BitluxBase, SharedCatalogMixin, table=True):
    """Airports. DATA_MODEL.md 3.4."""
    __tablename__ = "airports"
    __table_args__ = (
        *tenant_indexes("airports"),
        Index("uq_airports_client_icao", "client_id", "icao_code", unique=True, postgresql_nulls_not_distinct=True, postgresql_where=text("icao_code IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_airports_iata", "iata_code", postgresql_where=text("iata_code IS NOT NULL")),
        Index("ix_airports_search", "search_tsv", postgresql_using="gin"),
        Index("ix_airports_country_active", "country_code", "is_active"),
        Index("ix_airports_location", "location", postgresql_using="gist"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_airports_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_airports_longitude"),
        {"comment": "Airports. DATA_MODEL.md 3.4."},
    )

    icao_code: Optional[str] = Field(default=None, sa_column=Column("icao_code", CHAR(4)))
    iata_code: Optional[str] = Field(default=None, sa_column=Column("iata_code", CHAR(3)))
    local_code: Optional[str] = Field(default=None, sa_column=Column("local_code", Text))
    name: str = Field(sa_column=Column("name", Text, nullable=False))
    city: Optional[str] = Field(default=None, sa_column=Column("city", Text))
    region: Optional[str] = Field(default=None, sa_column=Column("region", Text))
    country_code: str = Field(sa_column=Column("country_code", CHAR(2), nullable=False))
    latitude: Decimal = Field(sa_column=Column("latitude", Numeric(9, 6), nullable=False))
    longitude: Decimal = Field(sa_column=Column("longitude", Numeric(9, 6), nullable=False))
    elevation_ft: Optional[int] = Field(default=None, sa_column=Column("elevation_ft", Integer))
    timezone: str = Field(sa_column=Column("timezone", Text, nullable=False))
    longest_runway_ft: Optional[int] = Field(default=None, sa_column=Column("longest_runway_ft", Integer))
    has_customs: bool = Field(default=False, sa_column=Column("has_customs", Boolean, nullable=False, server_default=text("false")))
    is_towered: Optional[bool] = Field(default=None, sa_column=Column("is_towered", Boolean))
    is_private: bool = Field(default=False, sa_column=Column("is_private", Boolean, nullable=False, server_default=text("false")))
    slot_restricted: bool = Field(default=False, sa_column=Column("slot_restricted", Boolean, nullable=False, server_default=text("false")))
    curfew: Optional[dict[str, Any]] = Field(default=None, sa_column=Column("curfew", JSONB))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, server_default=text("true")))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(name::text, '') || ' ' || coalesce(city::text, '') || ' ' || coalesce(icao_code::text, '') || ' ' || coalesce(iata_code::text, ''))", persisted=True)))
    # Core `point`, not PostGIS; planar prefilter only (DATA_MODEL 1.6).
    location: Optional[Any] = Field(default=None, sa_column=Column("location", POINT, Computed("point(longitude::float8, latitude::float8)", persisted=True)))

    fbos: list["FBO"] = Relationship(back_populates="airport", cascade_delete=True)


class FBO(BitluxBase, SharedCatalogMixin, table=True):
    """Fixed-base operators (ground handling). DATA_MODEL.md 3.4."""
    __tablename__ = "fbos"
    __table_args__ = (
        *tenant_indexes("fbos"),
        Index("uq_fbos_client_airport_name", "client_id", "airport_id", text("lower(name)"), unique=True, postgresql_nulls_not_distinct=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_fbos_airport", "airport_id"),
        Index("ix_fbos_preferred", "client_id", postgresql_where=text("is_preferred AND deleted_at IS NULL")),
        {"comment": "Fixed-base operators (ground handling). DATA_MODEL.md 3.4."},
    )

    airport_id: uuid.UUID = Field(sa_column=Column("airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="CASCADE"), nullable=False))
    name: str = Field(sa_column=Column("name", Text, nullable=False))
    brand: Optional[str] = Field(default=None, sa_column=Column("brand", Text))
    phone: Optional[str] = Field(default=None, sa_column=Column("phone", Text))
    unicom_frequency: Optional[str] = Field(default=None, sa_column=Column("unicom_frequency", Text))
    address_line: Optional[str] = Field(default=None, sa_column=Column("address_line", Text))
    fuel_brand: Optional[str] = Field(default=None, sa_column=Column("fuel_brand", Text))
    has_customs: bool = Field(default=False, sa_column=Column("has_customs", Boolean, nullable=False, server_default=text("false")))
    hours_of_operation: Optional[str] = Field(default=None, sa_column=Column("hours_of_operation", Text))
    is_preferred: bool = Field(default=False, sa_column=Column("is_preferred", Boolean, nullable=False, server_default=text("false")))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    airport: Optional["Airport"] = Relationship(back_populates="fbos")
