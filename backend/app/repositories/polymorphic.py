"""Resolve (entity_type, entity_id) pairs -- the schema's polymorphic edges.

document_links, entity_tags, tasks, activities, addresses and audit_logs all
point at "some row of some table" through this pair (DATA_MODEL.md 5,
"Polymorphism"). PostgreSQL cannot foreign-key that, so the trigger in
migration 013 validates it at the database. This module is the same check for
application code: ask before you link, get a typed row back, and produce a
proper error instead of a trigger's.

The trigger stays as the backstop. This is the front door.
"""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.models import TABLE_MODELS
from app.models.enums import EntityType

from .context import current_client_id

__all__ = ["ENTITY_TABLE_MAP", "ENTITY_MODEL_MAP", "EntityNotFound", "resolve_entity", "ensure_entity_exists", "entity_type_of"]

# Mirrors the CASE in migration 013's validate_polymorphic_ref(). Keep in step.
ENTITY_TABLE_MAP: dict[EntityType, str] = {
    EntityType.CLIENT: "clients",
    EntityType.USER: "users",
    EntityType.SEGMENT: "segments",
    EntityType.CONTACT: "contacts",
    EntityType.PASSENGER: "passengers",
    EntityType.ACCOUNT_HOLDER: "account_holders",
    EntityType.TRAVEL_DOCUMENT: "travel_documents",
    EntityType.MANUFACTURER: "manufacturers",
    EntityType.AIRCRAFT_MODEL: "aircraft_models",
    EntityType.AIRCRAFT: "aircraft",
    EntityType.OPERATOR: "operators",
    EntityType.OPERATOR_SAFETY_RATING: "operator_safety_ratings",
    EntityType.CREW_MEMBER: "crew_members",
    EntityType.AIRPORT: "airports",
    EntityType.FBO: "fbos",
    EntityType.TRIP: "trips",
    EntityType.LEG: "legs",
    EntityType.LEG_PASSENGER: "leg_passengers",
    EntityType.LEG_CREW: "leg_crew",
    EntityType.EMPTY_LEG: "empty_legs",
    EntityType.QUOTE: "quotes",
    EntityType.BOOKING: "bookings",
    EntityType.INVOICE: "invoices",
    EntityType.PAYMENT: "payments",
    EntityType.DOCUMENT: "documents",
    EntityType.TASK: "tasks",
    EntityType.ACTIVITY: "activities",
}
ENTITY_MODEL_MAP: dict[EntityType, type[SQLModel]] = {
    et: TABLE_MODELS[table] for et, table in ENTITY_TABLE_MAP.items()
}
_MODEL_TO_TYPE: dict[type[SQLModel], EntityType] = {m: et for et, m in ENTITY_MODEL_MAP.items()}

# Tables whose client_id may be NULL: a global row is a legitimate target for any tenant.
_SHARED_CATALOG = {"manufacturers", "aircraft_models", "airports", "fbos"}

assert set(ENTITY_TABLE_MAP) == set(EntityType), "ENTITY_TABLE_MAP must cover every EntityType"


class EntityNotFound(LookupError):
    def __init__(self, entity_type: EntityType, entity_id: uuid.UUID) -> None:
        super().__init__(
            f"{entity_type.value} {entity_id} does not exist, is soft-deleted, or belongs to another tenant"
        )
        self.entity_type, self.entity_id = entity_type, entity_id


def entity_type_of(obj: SQLModel | type[SQLModel]) -> EntityType:
    """The EntityType for a model instance or class -- e.g. to build a document link."""
    cls = obj if isinstance(obj, type) else type(obj)
    return _MODEL_TO_TYPE[cls]


async def resolve_entity(
    session: AsyncSession, entity_type: EntityType, entity_id: uuid.UUID
) -> Optional[SQLModel]:
    """The live, in-tenant row a polymorphic pair points at, or None.

    Same rules as the database trigger: not soft-deleted; and belongs to the
    current tenant, except that clients match on their own id and shared
    catalog rows may be global.
    """
    model = ENTITY_MODEL_MAP[entity_type]
    table = ENTITY_TABLE_MAP[entity_type]
    tenant = current_client_id()
    stmt = select(model).where(model.id == entity_id)
    if "deleted_at" in model.__table__.c:
        stmt = stmt.where(model.deleted_at.is_(None))
    if table == "clients":
        stmt = stmt.where(model.id == tenant)
    elif table in _SHARED_CATALOG:
        stmt = stmt.where(or_(model.client_id.is_(None), model.client_id == tenant))
    else:
        stmt = stmt.where(model.client_id == tenant)
    return (await session.execute(stmt)).scalar_one_or_none()


async def ensure_entity_exists(
    session: AsyncSession, entity_type: EntityType, entity_id: uuid.UUID
) -> SQLModel:
    """resolve_entity(), but a missing target is an error -- call before writing a link."""
    row = await resolve_entity(session, entity_type, entity_id)
    if row is None:
        raise EntityNotFound(entity_type, entity_id)
    return row
