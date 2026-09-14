"""Crew members (DATA_MODEL.md 3.5)."""

import uuid
from datetime import date
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import CHAR, CheckConstraint, Column, Computed, Date, ForeignKey, Index, Integer, LargeBinary, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TSVECTOR, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import CrewRole, CrewStatus

if TYPE_CHECKING:
    from .fleet import Operator


class CrewMember(BitluxBase, TenantScopedMixin, table=True):
    """Flight crew. DATA_MODEL.md 3.5."""
    __tablename__ = "crew_members"
    __table_args__ = (
        *tenant_indexes("crew_members"),
        Index("ix_crew_members_operator", "client_id", "operator_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_crew_members_status", "client_id", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_crew_members_type_ratings", "type_ratings", postgresql_using="gin"),
        Index("ix_crew_members_medical_expiry", "client_id", "medical_expiry", postgresql_where=text("status = 'active' AND deleted_at IS NULL")),
        Index("ix_crew_members_recurrent_due", "client_id", "next_recurrent_due", postgresql_where=text("status = 'active' AND deleted_at IS NULL")),
        Index("ix_crew_members_search", "search_tsv", postgresql_using="gin"),
        CheckConstraint("total_hours IS NULL OR total_hours >= 0", name="ck_crew_members_hours_nonneg"),
        {"comment": "Flight crew. DATA_MODEL.md 3.5."},
    )

    operator_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("operator_id", UUID(as_uuid=True), ForeignKey("operators.id", ondelete="SET NULL")))
    first_name: str = Field(sa_column=Column("first_name", Text, nullable=False))
    last_name: str = Field(sa_column=Column("last_name", Text, nullable=False))
    primary_role: CrewRole = Field(default=CrewRole.PIC, sa_column=Column("primary_role", pg_enum(CrewRole), nullable=False, server_default="pic"))
    status: CrewStatus = Field(default=CrewStatus.ACTIVE, sa_column=Column("status", pg_enum(CrewStatus), nullable=False, server_default="active"))
    date_of_birth: Optional[date] = Field(default=None, sa_column=Column("date_of_birth", Date))
    nationality_code: Optional[str] = Field(default=None, sa_column=Column("nationality_code", CHAR(2)))
    email: Optional[str] = Field(default=None, sa_column=Column("email", CITEXT))
    phone: Optional[str] = Field(default=None, sa_column=Column("phone", Text))
    license_number: Optional[bytes] = Field(default=None, sa_column=Column("license_number", LargeBinary))
    license_last4: Optional[str] = Field(default=None, sa_column=Column("license_last4", Text))
    license_type: Optional[str] = Field(default=None, sa_column=Column("license_type", Text))
    license_country: Optional[str] = Field(default=None, sa_column=Column("license_country", CHAR(2)))
    medical_class: Optional[str] = Field(default=None, sa_column=Column("medical_class", Text))
    medical_expiry: Optional[date] = Field(default=None, sa_column=Column("medical_expiry", Date))
    type_ratings: list[str] = Field(default_factory=list, sa_column=Column("type_ratings", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")))
    total_hours: Optional[int] = Field(default=None, sa_column=Column("total_hours", Integer))
    hours_on_type: dict[str, Any] = Field(default_factory=dict, sa_column=Column("hours_on_type", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    base_airport_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("base_airport_id", UUID(as_uuid=True), ForeignKey("airports.id", ondelete="SET NULL")))
    photo_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("photo_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_crew_members_photo")))
    last_recurrent_at: Optional[date] = Field(default=None, sa_column=Column("last_recurrent_at", Date))
    next_recurrent_due: Optional[date] = Field(default=None, sa_column=Column("next_recurrent_due", Date))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(first_name::text, '') || ' ' || coalesce(last_name::text, '') || ' ' || coalesce(email::text, ''))", persisted=True)))

    operator: Optional["Operator"] = Relationship(back_populates="crew_members")
