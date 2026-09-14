"""Fleet: Manufacturers -> Models -> Aircraft -> Operators (DATA_MODEL.md 3.3)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CHAR, CheckConstraint, column, Column, Computed, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, text, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, ExcludeConstraint, JSONB, TSVECTOR, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, SharedCatalogMixin, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import AircraftCategory, AircraftStatus, OperatorStatus, PaymentTerms, RegulatoryPart, SafetyProgram, SafetyRatingLevel

if TYPE_CHECKING:
    from .crew import CrewMember
    from .trips import Leg


class Manufacturer(BitluxBase, SharedCatalogMixin, table=True):
    """Aircraft manufacturers. DATA_MODEL.md 3.3."""
    __tablename__ = "manufacturers"
    __table_args__ = (
        *tenant_indexes("manufacturers"),
        Index("uq_manufacturers_client_name", "client_id", text("lower(name)"), unique=True, postgresql_nulls_not_distinct=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_manufacturers_name", text("lower(name)")),
        Index("ix_manufacturers_search", "search_tsv", postgresql_using="gin"),  # migration 016
        {"comment": "Aircraft manufacturers. DATA_MODEL.md 3.3."},
    )

    name: str = Field(sa_column=Column("name", Text, nullable=False))
    short_name: Optional[str] = Field(default=None, sa_column=Column("short_name", Text))
    code: Optional[str] = Field(default=None, sa_column=Column("code", CITEXT))
    country_code: Optional[str] = Field(default=None, sa_column=Column("country_code", CHAR(2)))
    website: Optional[str] = Field(default=None, sa_column=Column("website", Text))
    logo_url: Optional[str] = Field(default=None, sa_column=Column("logo_url", Text))
    founded_year: Optional[int] = Field(default=None, sa_column=Column("founded_year", SmallInteger))
    is_active: bool = Field(default=True, sa_column=Column("is_active", Boolean, nullable=False, server_default=text("true")))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(name::text, '') || ' ' || coalesce(short_name::text, '') || ' ' || coalesce(code::text, ''))", persisted=True)))  # migration 016

    models: list["AircraftModel"] = Relationship(back_populates="manufacturer")


class AircraftModel(BitluxBase, SharedCatalogMixin, table=True):
    """Aircraft types. DATA_MODEL.md 3.3."""
    __tablename__ = "aircraft_models"
    __table_args__ = (
        *tenant_indexes("aircraft_models"),
        Index("uq_aircraft_models_client_mfr_name", "client_id", "manufacturer_id", text("lower(name)"), unique=True, postgresql_nulls_not_distinct=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_aircraft_models_cat_pax", "category", "max_passengers"),
        Index("ix_aircraft_models_icao", "icao_type_code"),
        Index("ix_aircraft_models_mfr", "manufacturer_id"),
        Index("ix_aircraft_models_cat_range", "category", "range_nm"),
        Index("ix_aircraft_models_search", "search_tsv", postgresql_using="gin"),  # migration 016
        CheckConstraint("hourly_rate_low_cents IS NULL OR hourly_rate_high_cents IS NULL OR hourly_rate_high_cents >= hourly_rate_low_cents", name="ck_aircraft_models_rate_band"),
        {"comment": "Aircraft types. DATA_MODEL.md 3.3."},
    )

    manufacturer_id: uuid.UUID = Field(sa_column=Column("manufacturer_id", UUID(as_uuid=True), ForeignKey("manufacturers.id", ondelete="RESTRICT"), nullable=False))
    name: str = Field(sa_column=Column("name", Text, nullable=False))
    family: Optional[str] = Field(default=None, sa_column=Column("family", Text))
    icao_type_code: Optional[str] = Field(default=None, sa_column=Column("icao_type_code", Text))
    category: AircraftCategory = Field(sa_column=Column("category", pg_enum(AircraftCategory), nullable=False))
    max_passengers: Optional[int] = Field(default=None, sa_column=Column("max_passengers", SmallInteger))
    typical_passengers: Optional[int] = Field(default=None, sa_column=Column("typical_passengers", SmallInteger))
    range_nm: Optional[int] = Field(default=None, sa_column=Column("range_nm", Integer))
    cruise_speed_kt: Optional[int] = Field(default=None, sa_column=Column("cruise_speed_kt", Integer))
    max_altitude_ft: Optional[int] = Field(default=None, sa_column=Column("max_altitude_ft", Integer))
    baggage_capacity_cuft: Optional[int] = Field(default=None, sa_column=Column("baggage_capacity_cuft", Integer))
    cabin_length_in: Optional[Decimal] = Field(default=None, sa_column=Column("cabin_length_in", Numeric(6, 1)))
    cabin_width_in: Optional[Decimal] = Field(default=None, sa_column=Column("cabin_width_in", Numeric(6, 1)))
    cabin_height_in: Optional[Decimal] = Field(default=None, sa_column=Column("cabin_height_in", Numeric(6, 1)))
    has_lavatory: Optional[bool] = Field(default=None, sa_column=Column("has_lavatory", Boolean))
    has_enclosed_lavatory: Optional[bool] = Field(default=None, sa_column=Column("has_enclosed_lavatory", Boolean))
    wifi_available: Optional[bool] = Field(default=None, sa_column=Column("wifi_available", Boolean))
    cabin_crew_standard: bool = Field(default=False, sa_column=Column("cabin_crew_standard", Boolean, nullable=False, server_default=text("false")))
    hourly_rate_low_cents: Optional[int] = Field(default=None, sa_column=Column("hourly_rate_low_cents", BigInteger))
    hourly_rate_high_cents: Optional[int] = Field(default=None, sa_column=Column("hourly_rate_high_cents", BigInteger))
    production_start_year: Optional[int] = Field(default=None, sa_column=Column("production_start_year", SmallInteger))
    production_end_year: Optional[int] = Field(default=None, sa_column=Column("production_end_year", SmallInteger))
    image_url: Optional[str] = Field(default=None, sa_column=Column("image_url", Text))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(name::text, '') || ' ' || coalesce(family::text, '') || ' ' || coalesce(icao_type_code::text, ''))", persisted=True)))  # migration 016

    manufacturer: Optional["Manufacturer"] = Relationship(back_populates="models")
    aircraft: list["Aircraft"] = Relationship(back_populates="model")


class Operator(BitluxBase, TenantScopedMixin, table=True):
    """Charter operators / AOC holders. DATA_MODEL.md 3.3."""
    __tablename__ = "operators"
    __table_args__ = (
        *tenant_indexes("operators"),
        Index("uq_operators_code", "client_id", "operator_code", unique=True, postgresql_where=text("operator_code IS NOT NULL AND deleted_at IS NULL")),
        Index("uq_operators_legal_name", "client_id", text("lower(legal_name)"), unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_operators_status", "client_id", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_operators_preferred", "client_id", postgresql_where=text("is_preferred AND deleted_at IS NULL")),
        Index("ix_operators_insurance_expiry", "client_id", "insurance_expiry", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_operators_aoc_expiry", "client_id", "aoc_expiry", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_operators_search", "search_tsv", postgresql_using="gin"),
        CheckConstraint("status <> 'blacklisted' OR blocklist_reason IS NOT NULL", name="ck_operators_blocklist_reason"),
        CheckConstraint("commission_rate IS NULL OR commission_rate BETWEEN 0 AND 1", name="ck_operators_commission_rate"),
        {"comment": "Charter operators / AOC holders. DATA_MODEL.md 3.3."},
    )

    legal_name: str = Field(sa_column=Column("legal_name", Text, nullable=False))
    dba_name: Optional[str] = Field(default=None, sa_column=Column("dba_name", Text))
    operator_code: Optional[str] = Field(default=None, sa_column=Column("operator_code", CITEXT))
    status: OperatorStatus = Field(default=OperatorStatus.PROSPECT, sa_column=Column("status", pg_enum(OperatorStatus), nullable=False, server_default="prospect"))
    country_code: Optional[str] = Field(default=None, sa_column=Column("country_code", CHAR(2)))
    regulatory_part: Optional[RegulatoryPart] = Field(default=None, sa_column=Column("regulatory_part", pg_enum(RegulatoryPart)))
    aoc_number: Optional[str] = Field(default=None, sa_column=Column("aoc_number", Text))
    aoc_expiry: Optional[date] = Field(default=None, sa_column=Column("aoc_expiry", Date))
    fleet_size: int = Field(default=0, sa_column=Column("fleet_size", SmallInteger, nullable=False, server_default="0"))
    primary_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("primary_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    ops_email: Optional[str] = Field(default=None, sa_column=Column("ops_email", CITEXT))
    ops_phone: Optional[str] = Field(default=None, sa_column=Column("ops_phone", Text))
    ops_24h_phone: Optional[str] = Field(default=None, sa_column=Column("ops_24h_phone", Text))
    accounts_email: Optional[str] = Field(default=None, sa_column=Column("accounts_email", CITEXT))
    website: Optional[str] = Field(default=None, sa_column=Column("website", Text))
    insurance_expiry: Optional[date] = Field(default=None, sa_column=Column("insurance_expiry", Date))
    insurance_limit_cents: Optional[int] = Field(default=None, sa_column=Column("insurance_limit_cents", BigInteger))
    w9_on_file: bool = Field(default=False, sa_column=Column("w9_on_file", Boolean, nullable=False, server_default=text("false")))
    is_preferred: bool = Field(default=False, sa_column=Column("is_preferred", Boolean, nullable=False, server_default=text("false")))
    blocklist_reason: Optional[str] = Field(default=None, sa_column=Column("blocklist_reason", Text))
    commission_rate: Optional[Decimal] = Field(default=None, sa_column=Column("commission_rate", Numeric(5, 4)))
    payment_terms: PaymentTerms = Field(default=PaymentTerms.PREPAID, sa_column=Column("payment_terms", pg_enum(PaymentTerms), nullable=False, server_default="prepaid"))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(legal_name::text, '') || ' ' || coalesce(dba_name::text, '') || ' ' || coalesce(operator_code::text, ''))", persisted=True)))

    aircraft: list["Aircraft"] = Relationship(back_populates="operator")
    safety_ratings: list["OperatorSafetyRating"] = Relationship(back_populates="operator", cascade_delete=True)
    crew_members: list["CrewMember"] = Relationship(back_populates="operator")


class OperatorSafetyRating(BitluxBase, TenantScopedMixin, table=True):
    """ARGUS / Wyvern / IS-BAO ratings. DATA_MODEL.md 3.3."""
    __tablename__ = "operator_safety_ratings"
    __table_args__ = (
        *tenant_indexes("operator_safety_ratings"),
        Index("uq_safety_ratings_current", "operator_id", "program", unique=True, postgresql_where=text("is_current AND deleted_at IS NULL")),
        Index("ix_safety_ratings_operator", "client_id", "operator_id", "program"),
        Index("ix_safety_ratings_expiry", "client_id", "expiry_date", postgresql_where=text("is_current AND deleted_at IS NULL")),
        Index("ix_safety_ratings_level", "client_id", "rating_level"),
        CheckConstraint("expiry_date IS NULL OR issued_date IS NULL OR expiry_date > issued_date", name="ck_safety_ratings_date_order"),
        {"comment": "ARGUS / Wyvern / IS-BAO ratings. DATA_MODEL.md 3.3."},
    )

    operator_id: uuid.UUID = Field(sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="CASCADE"), nullable=False))
    program: SafetyProgram = Field(sa_column=Column("program", pg_enum(SafetyProgram), nullable=False))
    rating_level: SafetyRatingLevel = Field(sa_column=Column("rating_level", pg_enum(SafetyRatingLevel), nullable=False))
    rating_label: Optional[str] = Field(default=None, sa_column=Column("rating_label", Text))
    issued_date: Optional[date] = Field(default=None, sa_column=Column("issued_date", Date))
    expiry_date: Optional[date] = Field(default=None, sa_column=Column("expiry_date", Date))
    audit_reference: Optional[str] = Field(default=None, sa_column=Column("audit_reference", Text))
    auditor_name: Optional[str] = Field(default=None, sa_column=Column("auditor_name", Text))
    scope_notes: Optional[str] = Field(default=None, sa_column=Column("scope_notes", Text))
    is_current: bool = Field(default=True, sa_column=Column("is_current", Boolean, nullable=False, server_default=text("true")))
    report_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("report_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_safety_ratings_report")))
    verified_at: Optional[datetime] = Field(default=None, sa_column=Column("verified_at", TIMESTAMP(timezone=True)))
    verified_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("verified_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))

    operator: Optional["Operator"] = Relationship(back_populates="safety_ratings")


class Aircraft(BitluxBase, TenantScopedMixin, table=True):
    """Physical tail numbers. DATA_MODEL.md 3.3."""
    __tablename__ = "aircraft"
    __table_args__ = (
        *tenant_indexes("aircraft"),
        Index("uq_aircraft_tail", "client_id", "tail_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_aircraft_operator", "client_id", "operator_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_aircraft_model", "client_id", "aircraft_model_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_aircraft_availability", "client_id", "status", "is_available_for_charter", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_aircraft_home_base", "client_id", "home_base_airport_id"),
        Index("ix_aircraft_search", "search_tsv", postgresql_using="gin"),
        {"comment": "Physical tail numbers. DATA_MODEL.md 3.3."},
    )

    tail_number: str = Field(sa_column=Column("tail_number", CITEXT, nullable=False))
    serial_number: Optional[str] = Field(default=None, sa_column=Column("serial_number", Text))
    aircraft_model_id: uuid.UUID = Field(sa_column=Column("aircraft_model_id", UUID(as_uuid=True), ForeignKey("aircraft_models.id", ondelete="RESTRICT"), nullable=False))
    operator_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="SET NULL")))
    owner_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("owner_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    status: AircraftStatus = Field(default=AircraftStatus.ACTIVE, sa_column=Column("status", pg_enum(AircraftStatus), nullable=False, server_default="active"))
    year_of_manufacture: Optional[int] = Field(default=None, sa_column=Column("year_of_manufacture", SmallInteger))
    registration_country: Optional[str] = Field(default=None, sa_column=Column("registration_country", CHAR(2)))
    home_base_airport_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("home_base_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="SET NULL")))
    max_passengers: Optional[int] = Field(default=None, sa_column=Column("max_passengers", SmallInteger))
    configured_seats: Optional[int] = Field(default=None, sa_column=Column("configured_seats", SmallInteger))
    divans: Optional[int] = Field(default=None, sa_column=Column("divans", SmallInteger))
    berths: Optional[int] = Field(default=None, sa_column=Column("berths", SmallInteger))
    interior_refurb_year: Optional[int] = Field(default=None, sa_column=Column("interior_refurb_year", SmallInteger))
    exterior_refurb_year: Optional[int] = Field(default=None, sa_column=Column("exterior_refurb_year", SmallInteger))
    wifi_provider: Optional[str] = Field(default=None, sa_column=Column("wifi_provider", Text))
    amenities: dict[str, Any] = Field(default_factory=dict, sa_column=Column("amenities", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    pets_allowed: Optional[bool] = Field(default=None, sa_column=Column("pets_allowed", Boolean))
    smoking_allowed: bool = Field(default=False, sa_column=Column("smoking_allowed", Boolean, nullable=False, server_default=text("false")))
    lavatory_type: Optional[str] = Field(default=None, sa_column=Column("lavatory_type", Text))
    cargo_capacity_cuft: Optional[int] = Field(default=None, sa_column=Column("cargo_capacity_cuft", Integer))
    hourly_rate_cents: Optional[int] = Field(default=None, sa_column=Column("hourly_rate_cents", BigInteger))
    is_available_for_charter: bool = Field(default=True, sa_column=Column("is_available_for_charter", Boolean, nullable=False, server_default=text("true")))
    last_verified_at: Optional[datetime] = Field(default=None, sa_column=Column("last_verified_at", TIMESTAMP(timezone=True)))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(tail_number::text, '') || ' ' || coalesce(serial_number::text, ''))", persisted=True)))

    model: Optional["AircraftModel"] = Relationship(back_populates="aircraft")
    operator: Optional["Operator"] = Relationship(back_populates="aircraft")
    operator_assignments: list["AircraftOperatorAssignment"] = Relationship(back_populates="aircraft", cascade_delete=True)
    legs: list["Leg"] = Relationship(back_populates="aircraft")


class AircraftOperatorAssignment(BitluxBase, TenantScopedMixin, table=True):
    """Aircraft <-> operator tenure history. DATA_MODEL.md 3.3."""
    __tablename__ = "aircraft_operator_assignments"
    __table_args__ = (
        *tenant_indexes("aircraft_operator_assignments"),
        Index("uq_aoa_current", "aircraft_id", unique=True, postgresql_where=text("is_current AND deleted_at IS NULL")),
        Index("ix_aoa_aircraft", "client_id", "aircraft_id", text("effective_from DESC")),
        Index("ix_aoa_operator", "client_id", "operator_id"),
        CheckConstraint("effective_to IS NULL OR effective_to > effective_from", name="ck_aoa_date_order"),
        ExcludeConstraint((column("aircraft_id"), "="), (text("daterange(effective_from, effective_to, '[)')"), "&&"), using="gist", where=text("deleted_at IS NULL"), name="ex_aoa_no_overlap"),
        {"comment": "Aircraft <-> operator tenure history. DATA_MODEL.md 3.3."},
    )

    aircraft_id: uuid.UUID = Field(sa_column=Column("aircraft_id", UUID(as_uuid=True), ForeignKey("aircraft.id", ondelete="CASCADE"), nullable=False))
    operator_id: uuid.UUID = Field(sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="RESTRICT"), nullable=False))
    effective_from: date = Field(sa_column=Column("effective_from", Date, nullable=False))
    effective_to: Optional[date] = Field(default=None, sa_column=Column("effective_to", Date))
    is_current: bool = Field(default=True, sa_column=Column("is_current", Boolean, nullable=False, server_default=text("true")))
    management_agreement_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("management_agreement_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_aoa_mgmt_agreement")))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    aircraft: Optional["Aircraft"] = Relationship(back_populates="operator_assignments")
