"""SQLModel ORM for the Bitlux CRM.

Importing this package registers every table on ``SQLModel.metadata`` -- which is what
``alembic/env.py`` points ``target_metadata`` at. Module order mirrors the migration chain.
"""

from sqlmodel import SQLModel

from . import enums
from .base import (BitluxBase, IdMixin, OptionalTenantColumnMixin, SharedCatalogMixin, TenantColumnMixin, TenantScopedMixin, TimestampMixin, AuthoredMixin, pg_enum, uuid7, utcnow)
from .enums import *  # noqa: F401,F403
from .tenancy import Client, RefreshToken, User
from .crm import Segment, Contact, ContactChannel, Address, Passenger, AccountHolder, AccountHolderPassenger, TravelDocument
from .fleet import Manufacturer, AircraftModel, Operator, OperatorSafetyRating, Aircraft, AircraftOperatorAssignment
from .geography import Airport, FBO
from .crew import CrewMember
from .trips import Trip, Leg, LegPassenger, LegCrew
from .empty_legs import EmptyLeg
from .commerce import Quote, QuoteLineItem, Booking, Invoice, InvoiceLineItem, Payment
from .cross_cutting import Document, DocumentLink, Task, Activity, Tag, EntityTag
from .audit import AuditLog

__all__ = [
    "SQLModel", "enums", "BitluxBase", "IdMixin", "OptionalTenantColumnMixin", "SharedCatalogMixin", "TenantColumnMixin",
    "TenantScopedMixin", "TimestampMixin", "AuthoredMixin", "pg_enum", "uuid7", "utcnow",
    *enums.__all__,
    "Client", "User", "RefreshToken",
    "Segment", "Contact", "ContactChannel", "Address", "Passenger", "AccountHolder", "AccountHolderPassenger", "TravelDocument",
    "Manufacturer", "AircraftModel", "Operator", "OperatorSafetyRating", "Aircraft", "AircraftOperatorAssignment",
    "Airport", "FBO",
    "CrewMember",
    "Trip", "Leg", "LegPassenger", "LegCrew",
    "EmptyLeg",
    "Quote", "QuoteLineItem", "Booking", "Invoice", "InvoiceLineItem", "Payment",
    "Document", "DocumentLink", "Task", "Activity", "Tag", "EntityTag",
    "AuditLog",
]

TABLE_MODELS: dict[str, type[SQLModel]] = {
    "clients": Client,
    "users": User,
    "refresh_tokens": RefreshToken,
    "segments": Segment,
    "contacts": Contact,
    "contact_channels": ContactChannel,
    "addresses": Address,
    "passengers": Passenger,
    "account_holders": AccountHolder,
    "account_holder_passengers": AccountHolderPassenger,
    "travel_documents": TravelDocument,
    "manufacturers": Manufacturer,
    "aircraft_models": AircraftModel,
    "operators": Operator,
    "operator_safety_ratings": OperatorSafetyRating,
    "aircraft": Aircraft,
    "aircraft_operator_assignments": AircraftOperatorAssignment,
    "airports": Airport,
    "fbos": FBO,
    "crew_members": CrewMember,
    "trips": Trip,
    "legs": Leg,
    "leg_passengers": LegPassenger,
    "leg_crew": LegCrew,
    "empty_legs": EmptyLeg,
    "quotes": Quote,
    "quote_line_items": QuoteLineItem,
    "bookings": Booking,
    "invoices": Invoice,
    "invoice_line_items": InvoiceLineItem,
    "payments": Payment,
    "documents": Document,
    "document_links": DocumentLink,
    "tasks": Task,
    "activities": Activity,
    "tags": Tag,
    "entity_tags": EntityTag,
    "audit_logs": AuditLog,
}
