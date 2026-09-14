"""CRM spine: Segments -> Contacts -> Passengers -> Account Holders (DATA_MODEL.md 3.2)."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CHAR, CheckConstraint, Column, Computed, Date, ForeignKey, Index, Integer, LargeBinary, Numeric, text, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, CITEXT, JSONB, TSVECTOR, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, LTREE, TenantScopedMixin, pg_enum, tenant_indexes
from .enums import AccountStatus, AccountType, AddressType, ChannelType, ContactStatus, ContactType, EntityType, LeadSource, PassengerStatus, PaxRelationship, PaymentTerms, SegmentType, TravelDocumentType

if TYPE_CHECKING:
    from .commerce import Invoice, Payment
    from .cross_cutting import Activity
    from .trips import Trip


class Segment(BitluxBase, TenantScopedMixin, table=True):
    """Contact segmentation, hierarchical. DATA_MODEL.md 3.2."""
    __tablename__ = "segments"
    __table_args__ = (
        *tenant_indexes("segments"),
        Index("uq_segments_client_name", "client_id", text("lower(name)"), unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_segments_client_code", "client_id", "code", unique=True, postgresql_where=text("code IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_segments_parent", "client_id", "parent_segment_id"),
        Index("ix_segments_path", "path", postgresql_using="gist"),
        CheckConstraint("parent_segment_id <> id", name="ck_segments_no_self_parent"),
        {"comment": "Contact segmentation, hierarchical. DATA_MODEL.md 3.2."},
    )

    name: str = Field(sa_column=Column("name", Text, nullable=False))
    code: Optional[str] = Field(default=None, sa_column=Column("code", CITEXT))
    segment_type: SegmentType = Field(default=SegmentType.OTHER, sa_column=Column("segment_type", pg_enum(SegmentType), nullable=False, server_default="other"))
    description: Optional[str] = Field(default=None, sa_column=Column("description", Text))
    parent_segment_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("parent_segment_id", UUID(as_uuid=True), ForeignKey("segments.id", ondelete="SET NULL")))
    path: Optional[str] = Field(default=None, sa_column=Column("path", LTREE))
    color: Optional[str] = Field(default=None, sa_column=Column("color", Text))
    is_auto: bool = Field(default=False, sa_column=Column("is_auto", Boolean, nullable=False, server_default=text("false")))
    criteria: dict[str, Any] = Field(default_factory=dict, sa_column=Column("criteria", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    sort_order: int = Field(default=0, sa_column=Column("sort_order", Integer, nullable=False, server_default="0"))

    contacts: list["Contact"] = Relationship(back_populates="segment")


class Contact(BitluxBase, TenantScopedMixin, table=True):
    """People and companies in the CRM. DATA_MODEL.md 3.2."""
    __tablename__ = "contacts"
    __table_args__ = (
        *tenant_indexes("contacts"),
        Index("ix_contacts_status", "client_id", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_contacts_segment", "client_id", "segment_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_contacts_owner", "client_id", "owner_user_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_contacts_email", "client_id", "primary_email"),
        Index("ix_contacts_parent", "client_id", "parent_contact_id"),
        Index("ix_contacts_last_activity", "client_id", text("last_activity_at DESC")),
        Index("ix_contacts_search", "search_tsv", postgresql_using="gin"),
        CheckConstraint("contact_type <> 'company' OR company_name IS NOT NULL", name="ck_contacts_company_needs_name"),
        CheckConstraint("contact_type <> 'individual' OR last_name IS NOT NULL", name="ck_contacts_individual_needs_last_name"),
        CheckConstraint("parent_contact_id <> id", name="ck_contacts_no_self_parent"),
        CheckConstraint("referred_by_contact_id <> id", name="ck_contacts_no_self_referral"),
        {"comment": "People and companies in the CRM. DATA_MODEL.md 3.2."},
    )

    segment_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("segment_id", UUID(as_uuid=True), ForeignKey("segments.id", ondelete="SET NULL")))
    contact_type: ContactType = Field(default=ContactType.INDIVIDUAL, sa_column=Column("contact_type", pg_enum(ContactType), nullable=False, server_default="individual"))
    status: ContactStatus = Field(default=ContactStatus.LEAD, sa_column=Column("status", pg_enum(ContactStatus), nullable=False, server_default="lead"))
    salutation: Optional[str] = Field(default=None, sa_column=Column("salutation", Text))
    first_name: Optional[str] = Field(default=None, sa_column=Column("first_name", Text))
    middle_name: Optional[str] = Field(default=None, sa_column=Column("middle_name", Text))
    last_name: Optional[str] = Field(default=None, sa_column=Column("last_name", Text))
    suffix: Optional[str] = Field(default=None, sa_column=Column("suffix", Text))
    display_name: str = Field(sa_column=Column("display_name", Text, nullable=False))
    company_name: Optional[str] = Field(default=None, sa_column=Column("company_name", Text))
    job_title: Optional[str] = Field(default=None, sa_column=Column("job_title", Text))
    parent_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("parent_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    referred_by_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("referred_by_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    owner_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("owner_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    source: LeadSource = Field(default=LeadSource.OTHER, sa_column=Column("source", pg_enum(LeadSource), nullable=False, server_default="other"))
    primary_email: Optional[str] = Field(default=None, sa_column=Column("primary_email", CITEXT))
    primary_phone: Optional[str] = Field(default=None, sa_column=Column("primary_phone", Text))
    preferred_language: Optional[str] = Field(default=None, sa_column=Column("preferred_language", Text))
    lifetime_value_cents: int = Field(default=0, sa_column=Column("lifetime_value_cents", BigInteger, nullable=False, server_default="0"))
    trip_count: int = Field(default=0, sa_column=Column("trip_count", Integer, nullable=False, server_default="0"))
    last_activity_at: Optional[datetime] = Field(default=None, sa_column=Column("last_activity_at", TIMESTAMP(timezone=True)))
    do_not_contact: bool = Field(default=False, sa_column=Column("do_not_contact", Boolean, nullable=False, server_default=text("false")))
    vip_notes: Optional[str] = Field(default=None, sa_column=Column("vip_notes", Text))
    preferences: dict[str, Any] = Field(default_factory=dict, sa_column=Column("preferences", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(display_name::text, '') || ' ' || coalesce(company_name::text, '') || ' ' || coalesce(primary_email::text, '') || ' ' || coalesce(primary_phone::text, ''))", persisted=True)))

    segment: Optional["Segment"] = Relationship(back_populates="contacts")
    channels: list["ContactChannel"] = Relationship(back_populates="contact", cascade_delete=True)
    passengers: list["Passenger"] = Relationship(back_populates="contact")
    activities: list["Activity"] = Relationship(back_populates="contact")


class ContactChannel(BitluxBase, TenantScopedMixin, table=True):
    """A contact's emails / phones / handles. DATA_MODEL.md 3.2."""
    __tablename__ = "contact_channels"
    __table_args__ = (
        *tenant_indexes("contact_channels"),
        Index("uq_contact_channels_value", "contact_id", "channel_type", "value", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("uq_contact_channels_primary", "contact_id", "channel_type", unique=True, postgresql_where=text("is_primary AND deleted_at IS NULL")),
        Index("ix_contact_channels_value", "client_id", "value"),
        {"comment": "A contact's emails / phones / handles. DATA_MODEL.md 3.2."},
    )

    contact_id: uuid.UUID = Field(sa_column=Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False))
    channel_type: ChannelType = Field(sa_column=Column("channel_type", pg_enum(ChannelType), nullable=False))
    value: str = Field(sa_column=Column("value", CITEXT, nullable=False))
    label: Optional[str] = Field(default=None, sa_column=Column("label", Text))
    is_primary: bool = Field(default=False, sa_column=Column("is_primary", Boolean, nullable=False, server_default=text("false")))
    verified_at: Optional[datetime] = Field(default=None, sa_column=Column("verified_at", TIMESTAMP(timezone=True)))
    opted_out_at: Optional[datetime] = Field(default=None, sa_column=Column("opted_out_at", TIMESTAMP(timezone=True)))

    contact: Optional["Contact"] = Relationship(back_populates="channels")


class Address(BitluxBase, TenantScopedMixin, table=True):
    """Polymorphic postal addresses. DATA_MODEL.md 3.2."""
    __tablename__ = "addresses"
    __table_args__ = (
        *tenant_indexes("addresses"),
        Index("ix_addresses_owner", "client_id", "owner_type", "owner_id", postgresql_where=text("deleted_at IS NULL")),
        Index("uq_addresses_primary", "owner_type", "owner_id", "address_type", unique=True, postgresql_where=text("is_primary AND deleted_at IS NULL")),
        {"comment": "Polymorphic postal addresses. DATA_MODEL.md 3.2."},
    )

    owner_type: EntityType = Field(sa_column=Column("owner_type", pg_enum(EntityType), nullable=False))
    owner_id: uuid.UUID = Field(sa_column=Column("owner_id", UUID(as_uuid=True), nullable=False))
    address_type: AddressType = Field(default=AddressType.OTHER, sa_column=Column("address_type", pg_enum(AddressType), nullable=False, server_default="other"))
    line1: str = Field(sa_column=Column("line1", Text, nullable=False))
    line2: Optional[str] = Field(default=None, sa_column=Column("line2", Text))
    city: Optional[str] = Field(default=None, sa_column=Column("city", Text))
    region: Optional[str] = Field(default=None, sa_column=Column("region", Text))
    postal_code: Optional[str] = Field(default=None, sa_column=Column("postal_code", Text))
    country_code: str = Field(sa_column=Column("country_code", CHAR(2), nullable=False))
    latitude: Optional[Decimal] = Field(default=None, sa_column=Column("latitude", Numeric(9, 6)))
    longitude: Optional[Decimal] = Field(default=None, sa_column=Column("longitude", Numeric(9, 6)))
    is_primary: bool = Field(default=False, sa_column=Column("is_primary", Boolean, nullable=False, server_default=text("false")))


class Passenger(BitluxBase, TenantScopedMixin, table=True):
    """Flying identities. DATA_MODEL.md 3.2."""
    __tablename__ = "passengers"
    __table_args__ = (
        *tenant_indexes("passengers"),
        Index("ix_passengers_contact", "client_id", "contact_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_passengers_name", "client_id", text("lower(last_name)"), text("lower(first_name)")),
        Index("ix_passengers_dob", "client_id", "date_of_birth"),
        Index("ix_passengers_search", "search_tsv", postgresql_using="gin"),
        CheckConstraint("guardian_passenger_id <> id", name="ck_passengers_no_self_guardian"),
        CheckConstraint("weight_kg IS NULL OR weight_kg > 0", name="ck_passengers_weight_positive"),
        {"comment": "Flying identities. DATA_MODEL.md 3.2."},
    )

    contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    status: PassengerStatus = Field(default=PassengerStatus.ACTIVE, sa_column=Column("status", pg_enum(PassengerStatus), nullable=False, server_default="active"))
    first_name: str = Field(sa_column=Column("first_name", Text, nullable=False))
    middle_name: Optional[str] = Field(default=None, sa_column=Column("middle_name", Text))
    last_name: str = Field(sa_column=Column("last_name", Text, nullable=False))
    preferred_name: Optional[str] = Field(default=None, sa_column=Column("preferred_name", Text))
    suffix: Optional[str] = Field(default=None, sa_column=Column("suffix", Text))
    date_of_birth: Optional[date] = Field(default=None, sa_column=Column("date_of_birth", Date))
    nationality_code: Optional[str] = Field(default=None, sa_column=Column("nationality_code", CHAR(2)))
    gender_marker: Optional[str] = Field(default=None, sa_column=Column("gender_marker", Text))
    weight_kg: Optional[Decimal] = Field(default=None, sa_column=Column("weight_kg", Numeric(5, 1)))
    guardian_passenger_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("guardian_passenger_id", UUID(as_uuid=True), ForeignKey("passengers.id", ondelete="SET NULL")))
    dietary_restrictions: list[str] = Field(default_factory=list, sa_column=Column("dietary_restrictions", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")))
    allergies: list[str] = Field(default_factory=list, sa_column=Column("allergies", ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")))
    mobility_assistance: bool = Field(default=False, sa_column=Column("mobility_assistance", Boolean, nullable=False, server_default=text("false")))
    travels_with_pet: bool = Field(default=False, sa_column=Column("travels_with_pet", Boolean, nullable=False, server_default=text("false")))
    pet_details: Optional[dict[str, Any]] = Field(default=None, sa_column=Column("pet_details", JSONB))
    preferences: dict[str, Any] = Field(default_factory=dict, sa_column=Column("preferences", JSONB, nullable=False, server_default=text("'{}'::jsonb")))
    known_traveler_number: Optional[bytes] = Field(default=None, sa_column=Column("known_traveler_number", LargeBinary))
    ktn_last4: Optional[str] = Field(default=None, sa_column=Column("ktn_last4", Text))
    redress_number: Optional[bytes] = Field(default=None, sa_column=Column("redress_number", LargeBinary))
    emergency_contact_name: Optional[str] = Field(default=None, sa_column=Column("emergency_contact_name", Text))
    emergency_contact_phone: Optional[str] = Field(default=None, sa_column=Column("emergency_contact_phone", Text))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))
    search_tsv: Optional[Any] = Field(default=None, sa_column=Column("search_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(first_name::text, '') || ' ' || coalesce(last_name::text, '') || ' ' || coalesce(preferred_name::text, ''))", persisted=True)))

    contact: Optional["Contact"] = Relationship(back_populates="passengers")
    travel_documents: list["TravelDocument"] = Relationship(back_populates="passenger")
    account_links: list["AccountHolderPassenger"] = Relationship(back_populates="passenger")


class AccountHolder(BitluxBase, TenantScopedMixin, table=True):
    """The commercial / billing entity -- who pays. DATA_MODEL.md 3.2."""
    __tablename__ = "account_holders"
    __table_args__ = (
        *tenant_indexes("account_holders"),
        Index("uq_account_holders_number", "client_id", "account_number", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_account_holders_status", "client_id", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_account_holders_contact", "client_id", "primary_contact_id"),
        Index("ix_account_holders_owner", "client_id", "owner_user_id"),
        Index("ix_account_holders_balance", "client_id", "balance_cents", postgresql_where=text("balance_cents > 0")),
        CheckConstraint("credit_limit_cents >= 0", name="ck_account_holders_credit_limit_nonneg"),
        {"comment": "The commercial / billing entity -- who pays. DATA_MODEL.md 3.2."},
    )

    account_number: str = Field(sa_column=Column("account_number", CITEXT, nullable=False))
    name: str = Field(sa_column=Column("name", Text, nullable=False))
    account_type: AccountType = Field(default=AccountType.INDIVIDUAL, sa_column=Column("account_type", pg_enum(AccountType), nullable=False, server_default="individual"))
    status: AccountStatus = Field(default=AccountStatus.PENDING, sa_column=Column("status", pg_enum(AccountStatus), nullable=False, server_default="pending"))
    primary_contact_id: uuid.UUID = Field(sa_column=Column("primary_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False))
    billing_contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("billing_contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="SET NULL")))
    owner_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("owner_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    currency: str = Field(default="USD", sa_column=Column("currency", CHAR(3), nullable=False, server_default="USD"))
    payment_terms: PaymentTerms = Field(default=PaymentTerms.PREPAID, sa_column=Column("payment_terms", pg_enum(PaymentTerms), nullable=False, server_default="prepaid"))
    credit_limit_cents: int = Field(default=0, sa_column=Column("credit_limit_cents", BigInteger, nullable=False, server_default="0"))
    balance_cents: int = Field(default=0, sa_column=Column("balance_cents", BigInteger, nullable=False, server_default="0"))
    prepaid_balance_cents: int = Field(default=0, sa_column=Column("prepaid_balance_cents", BigInteger, nullable=False, server_default="0"))
    tax_id: Optional[bytes] = Field(default=None, sa_column=Column("tax_id", LargeBinary))
    tax_id_last4: Optional[str] = Field(default=None, sa_column=Column("tax_id_last4", Text))
    tax_exempt: bool = Field(default=False, sa_column=Column("tax_exempt", Boolean, nullable=False, server_default=text("false")))
    billing_address_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("billing_address_id", UUID(as_uuid=True), ForeignKey("addresses.id", ondelete="SET NULL")))
    contract_signed_at: Optional[datetime] = Field(default=None, sa_column=Column("contract_signed_at", TIMESTAMP(timezone=True)))
    credit_reviewed_at: Optional[datetime] = Field(default=None, sa_column=Column("credit_reviewed_at", TIMESTAMP(timezone=True)))
    notes: Optional[str] = Field(default=None, sa_column=Column("notes", Text))

    passenger_links: list["AccountHolderPassenger"] = Relationship(back_populates="account_holder")
    trips: list["Trip"] = Relationship(back_populates="account_holder")
    invoices: list["Invoice"] = Relationship(back_populates="account_holder")
    payments: list["Payment"] = Relationship(back_populates="account_holder")


class AccountHolderPassenger(BitluxBase, TenantScopedMixin, table=True):
    """Which passengers may fly on which account. DATA_MODEL.md 3.2."""
    __tablename__ = "account_holder_passengers"
    __table_args__ = (
        *tenant_indexes("account_holder_passengers"),
        Index("uq_ahp_account_passenger", "account_holder_id", "passenger_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_ahp_passenger", "client_id", "passenger_id"),
        CheckConstraint("valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from", name="ck_ahp_valid_range"),
        {"comment": "Which passengers may fly on which account. DATA_MODEL.md 3.2."},
    )

    account_holder_id: uuid.UUID = Field(sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="CASCADE"), nullable=False))
    passenger_id: uuid.UUID = Field(sa_column=Column("passenger_id", UUID(as_uuid=True), ForeignKey("passengers.id", ondelete="CASCADE"), nullable=False))
    relationship: PaxRelationship = Field(default=PaxRelationship.OTHER, sa_column=Column("relationship", pg_enum(PaxRelationship), nullable=False, server_default="other"))
    is_authorized_booker: bool = Field(default=False, sa_column=Column("is_authorized_booker", Boolean, nullable=False, server_default=text("false")))
    spend_limit_cents: Optional[int] = Field(default=None, sa_column=Column("spend_limit_cents", BigInteger))
    valid_from: Optional[date] = Field(default=None, sa_column=Column("valid_from", Date))
    valid_to: Optional[date] = Field(default=None, sa_column=Column("valid_to", Date))

    account_holder: Optional["AccountHolder"] = Relationship(back_populates="passenger_links")
    passenger: Optional["Passenger"] = Relationship(back_populates="account_links")


class TravelDocument(BitluxBase, TenantScopedMixin, table=True):
    """Passports, visas, crew licences. DATA_MODEL.md 3.2."""
    __tablename__ = "travel_documents"
    __table_args__ = (
        *tenant_indexes("travel_documents"),
        Index("ix_travel_documents_passenger", "client_id", "passenger_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_travel_documents_crew", "client_id", "crew_member_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_travel_documents_expiry", "client_id", "expiry_date", postgresql_where=text("deleted_at IS NULL")),
        Index("uq_travel_documents_primary", "passenger_id", "document_type", unique=True, postgresql_where=text("is_primary AND deleted_at IS NULL")),
        CheckConstraint("num_nonnulls(passenger_id, crew_member_id) = 1", name="ck_travel_documents_exclusive_arc"),
        CheckConstraint("expiry_date IS NULL OR issue_date IS NULL OR expiry_date > issue_date", name="ck_travel_documents_date_order"),
        {"comment": "Passports, visas, crew licences. DATA_MODEL.md 3.2."},
    )

    passenger_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("passenger_id", UUID(as_uuid=True), ForeignKey("passengers.id", ondelete="CASCADE")))
    crew_member_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("crew_member_id", UUID(as_uuid=True), ForeignKey("crew_members.id", ondelete="CASCADE", name="fk_travel_documents_crew")))
    document_type: TravelDocumentType = Field(sa_column=Column("document_type", pg_enum(TravelDocumentType), nullable=False))
    number: bytes = Field(sa_column=Column("number", LargeBinary, nullable=False))
    number_last4: str = Field(sa_column=Column("number_last4", Text, nullable=False))
    full_name_on_document: str = Field(sa_column=Column("full_name_on_document", Text, nullable=False))
    issuing_country: str = Field(sa_column=Column("issuing_country", CHAR(2), nullable=False))
    nationality_code: Optional[str] = Field(default=None, sa_column=Column("nationality_code", CHAR(2)))
    place_of_birth: Optional[str] = Field(default=None, sa_column=Column("place_of_birth", Text))
    issue_date: Optional[date] = Field(default=None, sa_column=Column("issue_date", Date))
    expiry_date: Optional[date] = Field(default=None, sa_column=Column("expiry_date", Date))
    scan_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("scan_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL", name="fk_travel_documents_scan")))
    verified_at: Optional[datetime] = Field(default=None, sa_column=Column("verified_at", TIMESTAMP(timezone=True)))
    verified_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("verified_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    is_primary: bool = Field(default=False, sa_column=Column("is_primary", Boolean, nullable=False, server_default=text("false")))

    passenger: Optional["Passenger"] = Relationship(back_populates="travel_documents")
