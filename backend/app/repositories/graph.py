"""The relational neighbourhood of an entity, for the D3 visualiser.

``GraphResolver`` knows, per node type, which foreign keys to walk: to-one
columns, to-many back-references, M:N junctions, and the polymorphic
document_links. It breadth-first expands from the root to ``depth`` hops,
skips node types the caller may not view, and refuses (GraphTooLarge) rather
than return a hairball once ``max_nodes`` is exceeded.

Node ``type`` is the singular table name -- broader than EntityType, because
the brief wants contact_channels and line items as nodes and those are not
polymorphic targets.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.models import (
    FBO, AccountHolder, AccountHolderPassenger, Activity, Aircraft, AircraftModel, Airport, Booking, Client, Contact,
    ContactChannel, CrewMember, Document, DocumentLink, EmptyLeg, Invoice, InvoiceLineItem, Leg, LegCrew, LegPassenger,
    Manufacturer, Operator, OperatorSafetyRating, Passenger, Payment, Quote, QuoteLineItem, Segment, Task,
    TravelDocument, Trip, User,
)
from app.models.enums import EntityType

from .base import NotFound, RepositoryError
from .context import current_client_id
from .polymorphic import ENTITY_MODEL_MAP

__all__ = ["GraphResolver", "GRAPH_TYPES", "Node", "Edge", "GraphTooLarge", "UnknownGraphType"]


class GraphTooLarge(RepositoryError):
    """The neighbourhood exceeds max_nodes; the caller should reduce depth."""

    def __init__(self, message: str, *, max_nodes: int, depth: int) -> None:
        super().__init__(message)
        self.max_nodes, self.depth = max_nodes, depth


class UnknownGraphType(RepositoryError):
    def __init__(self, type_name: str) -> None:
        super().__init__(f"Unknown entity type '{type_name}'")
        self.type_name = type_name

_SHARED_CATALOG = {"manufacturers", "aircraft_models", "airports", "fbos"}


@dataclass(frozen=True)
class Node:
    id: str
    type: str
    label: str
    subtitle: Optional[str]
    url: str


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    type: str
    label: str

    def as_json(self) -> dict[str, str]:
        return {"from": self.source, "to": self.target, "type": self.type, "label": self.label}


# ---------------------------------------------------------------- node presentation
def _money(cents: int | None, cur: str = "") -> str:
    return f"{(cents or 0) / 100:,.2f} {cur}".strip()


@dataclass(frozen=True)
class _NodeType:
    model: type[SQLModel]
    permission: str
    label: Callable[[Any], str]
    subtitle: Callable[[Any], Optional[str]]

    @property
    def table(self) -> str:
        return self.model.__tablename__  # type: ignore[return-value]


GRAPH_TYPES: dict[str, _NodeType] = {
    "client": _NodeType(Client, "clients.view", lambda r: r.name, lambda r: r.slug),
    "user": _NodeType(User, "users.view", lambda r: r.full_name, lambda r: f"{r.role.value} · {r.email}"),
    "segment": _NodeType(Segment, "segments.view", lambda r: r.name, lambda r: r.segment_type.value),
    "contact": _NodeType(Contact, "contacts.view", lambda r: r.display_name,
                         lambda r: ", ".join(x for x in (r.job_title, r.company_name if r.contact_type.value == "individual" else None) if x) or r.primary_email),
    "contact_channel": _NodeType(ContactChannel, "contacts.view", lambda r: r.value, lambda r: r.channel_type.value),
    "passenger": _NodeType(Passenger, "passengers.view", lambda r: f"{r.first_name} {r.last_name}", lambda r: r.nationality_code),
    "travel_document": _NodeType(TravelDocument, "passengers.view", lambda r: f"{r.document_type.value} ····{r.number_last4}", lambda r: f"expires {r.expiry_date}" if r.expiry_date else None),
    "account_holder": _NodeType(AccountHolder, "account_holders.view", lambda r: r.name, lambda r: r.account_number),
    "manufacturer": _NodeType(Manufacturer, "manufacturers.view", lambda r: r.name, lambda r: r.country_code),
    "aircraft_model": _NodeType(AircraftModel, "aircraft_models.view", lambda r: r.name, lambda r: r.category.value.replace("_", " ")),
    "aircraft": _NodeType(Aircraft, "aircraft.view", lambda r: r.tail_number, lambda r: r.status.value),
    "operator": _NodeType(Operator, "operators.view", lambda r: r.dba_name or r.legal_name, lambda r: r.status.value),
    "operator_safety_rating": _NodeType(OperatorSafetyRating, "operators.view", lambda r: r.rating_label or r.rating_level.value, lambda r: f"expires {r.expiry_date}" if r.expiry_date else None),
    "crew_member": _NodeType(CrewMember, "crew.view", lambda r: f"{r.first_name} {r.last_name}", lambda r: r.primary_role.value.upper()),
    "airport": _NodeType(Airport, "airports.view", lambda r: r.icao_code or r.iata_code or r.name, lambda r: r.name),
    "fbo": _NodeType(FBO, "airports.view", lambda r: r.name, lambda r: r.brand),
    "trip": _NodeType(Trip, "trips.view", lambda r: r.trip_number, lambda r: f"{r.status.value} · {r.departure_date or ''}".strip(" ·")),
    "leg": _NodeType(Leg, "legs.view", lambda r: f"Leg {r.leg_number}", lambda r: f"{r.scheduled_departure_at:%Y-%m-%d %H:%M}Z"),
    "empty_leg": _NodeType(EmptyLeg, "empty_legs.view", lambda r: f"Empty leg · {_money(r.asking_price_cents, r.currency)}", lambda r: f"{r.earliest_departure_at:%Y-%m-%d}"),
    "quote": _NodeType(Quote, "quotes.view", lambda r: f"{r.quote_number} r{r.revision}", lambda r: f"{r.status.value} · {_money(r.total_cents, r.currency)}"),
    "quote_line_item": _NodeType(QuoteLineItem, "quotes.view", lambda r: r.description, lambda r: _money(r.sell_cents)),
    "booking": _NodeType(Booking, "bookings.view", lambda r: r.booking_number, lambda r: r.status.value),
    "invoice": _NodeType(Invoice, "invoices.view", lambda r: r.invoice_number, lambda r: f"{r.status.value} · balance {_money(r.balance_cents, r.currency)}"),
    "invoice_line_item": _NodeType(InvoiceLineItem, "invoices.view", lambda r: r.description, lambda r: _money(r.amount_cents)),
    "payment": _NodeType(Payment, "payments.view", lambda r: _money(r.amount_cents, r.currency), lambda r: f"{r.method.value} · {r.status.value}"),
    "document": _NodeType(Document, "documents.view", lambda r: r.title, lambda r: r.document_type.value.replace("_", " ")),
    "task": _NodeType(Task, "tasks.view", lambda r: r.title, lambda r: f"{r.status.value} · {r.priority.value}"),
    "activity": _NodeType(Activity, "activities.view", lambda r: r.subject or r.activity_type.value, lambda r: f"{r.activity_type.value} · {r.occurred_at:%Y-%m-%d}"),
}
_TYPE_OF_MODEL: dict[type, str] = {t.model: name for name, t in GRAPH_TYPES.items()}


# ------------------------------------------------------------------- edge specs
@dataclass(frozen=True)
class ToOne:
    column: str          # FK column on the source model
    target: str          # node type
    type: str
    label: str


@dataclass(frozen=True)
class ToMany:
    target: str          # node type whose model has the FK
    column: str          # FK column on the target model pointing at the source
    type: str
    label: str


@dataclass(frozen=True)
class Via:
    junction: type[SQLModel]
    src_column: str      # junction column -> source id
    dst_column: str      # junction column -> target id
    target: str
    type: str
    label: str


@dataclass(frozen=True)
class Documents:
    entity_type: EntityType


@dataclass(frozen=True)
class PolymorphicSubject:
    """The row an (entity_type, entity_id) pair on the source points at."""
    type_column: str = "entity_type"
    id_column: str = "entity_id"
    type: str = "about"
    label: str = "about"


@dataclass(frozen=True)
class LinkedEntities:
    """Reverse of Documents: everything a document is attached to."""


EDGES: dict[str, list[Any]] = {
    "client": [ToMany("segment", "client_id", "has_segment", "segment"), ToMany("contact", "client_id", "has_contact", "contact"),
               ToMany("account_holder", "client_id", "has_account", "account"), ToMany("trip", "client_id", "has_trip", "trip")],
    "segment": [ToOne("parent_segment_id", "segment", "parent", "parent segment"), ToMany("contact", "segment_id", "member", "member")],
    "contact": [ToOne("segment_id", "segment", "in_segment", "in segment"), ToMany("contact_channel", "contact_id", "channel", "channel"),
                ToMany("passenger", "contact_id", "flies_as", "flies as"), ToMany("account_holder", "primary_contact_id", "primary_contact_of", "primary contact of"),
                ToMany("activity", "contact_id", "activity", "activity"), ToOne("parent_contact_id", "contact", "works_at", "works at")],
    "contact_channel": [ToOne("contact_id", "contact", "belongs_to", "belongs to")],
    "passenger": [ToOne("contact_id", "contact", "is_contact", "contact record"), ToMany("travel_document", "passenger_id", "document", "travel document"),
                  Via(AccountHolderPassenger, "passenger_id", "account_holder_id", "account_holder", "may_fly_on", "may fly on"),
                  Via(LegPassenger, "passenger_id", "leg_id", "leg", "flew_on", "manifested on")],
    "travel_document": [ToOne("passenger_id", "passenger", "belongs_to", "belongs to")],
    "account_holder": [ToOne("primary_contact_id", "contact", "primary_contact", "primary contact"), ToOne("billing_contact_id", "contact", "billing_contact", "billing contact"),
                       Via(AccountHolderPassenger, "account_holder_id", "passenger_id", "passenger", "authorises", "authorised passenger"),
                       ToMany("trip", "account_holder_id", "trip", "trip"), ToMany("quote", "account_holder_id", "quote", "quote"),
                       ToMany("invoice", "account_holder_id", "invoice", "invoice"), ToMany("payment", "account_holder_id", "payment", "payment")],
    "manufacturer": [ToMany("aircraft_model", "manufacturer_id", "builds", "builds")],
    "aircraft_model": [ToOne("manufacturer_id", "manufacturer", "built_by", "built by"), ToMany("aircraft", "aircraft_model_id", "example", "tail")],
    "aircraft": [ToOne("aircraft_model_id", "aircraft_model", "is_model", "type"), ToOne("operator_id", "operator", "operated_by", "operated by"),
                 ToMany("leg", "aircraft_id", "flies", "leg"), ToMany("empty_leg", "aircraft_id", "offers", "empty leg"), Documents(EntityType.AIRCRAFT)],
    "operator": [ToMany("aircraft", "operator_id", "operates", "operates"), ToMany("crew_member", "operator_id", "employs", "crew"),
                 ToMany("operator_safety_rating", "operator_id", "rated", "safety rating"), ToMany("empty_leg", "operator_id", "offers", "empty leg"),
                 Documents(EntityType.OPERATOR)],
    "operator_safety_rating": [ToOne("operator_id", "operator", "rates", "rates")],
    "crew_member": [ToOne("operator_id", "operator", "employed_by", "employed by"), Via(LegCrew, "crew_member_id", "leg_id", "leg", "crewed", "duty")],
    "airport": [ToMany("fbo", "airport_id", "fbo", "FBO")],
    "fbo": [ToOne("airport_id", "airport", "at", "at")],
    "trip": [ToOne("account_holder_id", "account_holder", "billed_to", "account"), ToOne("primary_contact_id", "contact", "contact", "contact"),
             ToOne("lead_passenger_id", "passenger", "lead_passenger", "lead passenger"), ToMany("leg", "trip_id", "leg", "leg"),
             ToMany("quote", "trip_id", "quoted", "quote"), ToMany("booking", "trip_id", "booked", "booking"), ToMany("invoice", "trip_id", "invoiced", "invoice"),
             Documents(EntityType.TRIP), ToOne("source_empty_leg_id", "empty_leg", "sourced_from", "sourced from empty leg")],
    "leg": [ToOne("trip_id", "trip", "part_of", "part of"), ToOne("departure_airport_id", "airport", "departs", "departs"),
            ToOne("arrival_airport_id", "airport", "arrives", "arrives"), ToOne("aircraft_id", "aircraft", "flown_by", "aircraft"),
            ToOne("operator_id", "operator", "operated_by", "operator"),
            Via(LegPassenger, "leg_id", "passenger_id", "passenger", "manifest", "manifest"), Via(LegCrew, "leg_id", "crew_member_id", "crew_member", "crew", "crew")],
    "empty_leg": [ToOne("operator_id", "operator", "offered_by", "operator"), ToOne("aircraft_id", "aircraft", "on", "aircraft"),
                  ToOne("departure_airport_id", "airport", "departs", "departs"), ToOne("arrival_airport_id", "airport", "arrives", "arrives"),
                  ToOne("booked_trip_id", "trip", "booked_as", "booked as")],
    "quote": [ToMany("quote_line_item", "quote_id", "line_item", "line item"), ToOne("trip_id", "trip", "for_trip", "trip"),
              ToMany("booking", "quote_id", "accepted_as", "booking"), ToOne("account_holder_id", "account_holder", "for_account", "account"),
              ToOne("parent_quote_id", "quote", "supersedes", "supersedes"), Documents(EntityType.QUOTE)],
    "quote_line_item": [ToOne("quote_id", "quote", "on_quote", "quote")],
    "booking": [ToOne("trip_id", "trip", "for_trip", "trip"), ToOne("quote_id", "quote", "from_quote", "quote"),
                ToOne("account_holder_id", "account_holder", "for_account", "account"), ToMany("invoice", "booking_id", "invoiced", "invoice"),
                Documents(EntityType.BOOKING)],
    "invoice": [ToMany("invoice_line_item", "invoice_id", "line_item", "line item"), ToMany("payment", "invoice_id", "paid_by", "payment"),
                ToOne("account_holder_id", "account_holder", "bills", "account"), ToOne("booking_id", "booking", "for_booking", "booking"),
                ToOne("trip_id", "trip", "for_trip", "trip"), Documents(EntityType.INVOICE)],
    "invoice_line_item": [ToOne("invoice_id", "invoice", "on_invoice", "invoice")],
    "payment": [ToOne("invoice_id", "invoice", "pays", "invoice"), ToOne("account_holder_id", "account_holder", "from_account", "account")],
    "document": [LinkedEntities()],
    "task": [PolymorphicSubject(), ToOne("assigned_to_user_id", "user", "assigned_to", "assigned to")],
    "activity": [ToOne("contact_id", "contact", "with", "with"), PolymorphicSubject(), ToOne("user_id", "user", "logged_by", "logged by")],
    "user": [],
}
_ENTITY_TYPE_TO_NODE = {et: _TYPE_OF_MODEL[m] for et, m in ENTITY_MODEL_MAP.items() if m in _TYPE_OF_MODEL}


class GraphResolver:
    def __init__(self, session: AsyncSession, can_view: Callable[[str], bool] = lambda perm: True, max_nodes: int = 200) -> None:
        self.session = session
        self.can_view = can_view
        self.max_nodes = max_nodes

    # ---------------------------------------------------------------- scoping
    def _scoped(self, model: type[SQLModel]):
        """Live + tenant-scoped SELECT, same rules as polymorphic.resolve_entity()."""
        tenant = current_client_id()
        stmt = select(model)
        if "deleted_at" in model.__table__.c:
            stmt = stmt.where(model.deleted_at.is_(None))
        table = model.__tablename__
        if table == "clients":
            stmt = stmt.where(model.id == tenant)
        elif table in _SHARED_CATALOG:
            stmt = stmt.where(or_(model.client_id.is_(None), model.client_id == tenant))
        elif "client_id" in model.__table__.c:
            stmt = stmt.where(model.client_id == tenant)
        return stmt

    async def _rows(self, model, *where) -> list[Any]:
        return list((await self.session.execute(self._scoped(model).where(*where))).scalars().all())

    def _node(self, type_name: str, row: Any) -> Node:
        t = GRAPH_TYPES[type_name]
        return Node(str(row.id), type_name, t.label(row), t.subtitle(row), f"/{t.table}/{row.id}")

    # ------------------------------------------------------------- expansion
    async def _neighbours(self, type_name: str, row: Any) -> list[tuple[str, Any, str, str, bool]]:
        """(target type, target row, edge type, edge label, outbound?) for one node."""
        out: list[tuple[str, Any, str, str, bool]] = []
        for spec in EDGES.get(type_name, []):
            if isinstance(spec, ToOne):
                target_id = getattr(row, spec.column)
                if target_id is None or not self._visible(spec.target):
                    continue
                for r in await self._rows(GRAPH_TYPES[spec.target].model, GRAPH_TYPES[spec.target].model.id == target_id):
                    out.append((spec.target, r, spec.type, spec.label, True))
            elif isinstance(spec, ToMany):
                if not self._visible(spec.target):
                    continue
                model = GRAPH_TYPES[spec.target].model
                for r in await self._rows(model, getattr(model, spec.column) == row.id):
                    out.append((spec.target, r, spec.type, spec.label, True))
            elif isinstance(spec, Via):
                if not self._visible(spec.target):
                    continue
                target_model = GRAPH_TYPES[spec.target].model
                links = await self._rows(spec.junction, getattr(spec.junction, spec.src_column) == row.id)
                ids = [getattr(link, spec.dst_column) for link in links]
                if ids:
                    for r in await self._rows(target_model, target_model.id.in_(ids)):
                        out.append((spec.target, r, spec.type, spec.label, True))
            elif isinstance(spec, Documents):
                if not self._visible("document"):
                    continue
                links = await self._rows(DocumentLink, DocumentLink.entity_type == spec.entity_type, DocumentLink.entity_id == row.id)
                ids = [link.document_id for link in links]
                if ids:
                    for r in await self._rows(Document, Document.id.in_(ids)):
                        out.append(("document", r, "attached", "document", True))
            elif isinstance(spec, LinkedEntities):
                for link in await self._rows(DocumentLink, DocumentLink.document_id == row.id):
                    node_type = _ENTITY_TYPE_TO_NODE.get(link.entity_type)
                    if node_type and self._visible(node_type):
                        model = GRAPH_TYPES[node_type].model
                        for r in await self._rows(model, model.id == link.entity_id):
                            out.append((node_type, r, "attached_to", link.link_role, True))
            elif isinstance(spec, PolymorphicSubject):
                et, eid = getattr(row, spec.type_column), getattr(row, spec.id_column)
                node_type = _ENTITY_TYPE_TO_NODE.get(et) if et else None
                if node_type and eid and self._visible(node_type):
                    model = GRAPH_TYPES[node_type].model
                    for r in await self._rows(model, model.id == eid):
                        out.append((node_type, r, spec.type, spec.label, True))
        return out

    def _visible(self, type_name: str) -> bool:
        return self.can_view(GRAPH_TYPES[type_name].permission)

    # ------------------------------------------------------------------ API
    async def neighbourhood(self, type_name: str, root_id: uuid.UUID, depth: int = 1) -> dict[str, list[dict[str, Any]]]:
        if type_name not in GRAPH_TYPES:
            raise UnknownGraphType(type_name)
        model = GRAPH_TYPES[type_name].model
        if not self._visible(type_name):
            raise NotFound(model, root_id)  # invisible == absent; nothing leaks
        root_rows = await self._rows(model, model.id == root_id)
        if not root_rows:
            raise NotFound(model, root_id)

        nodes: dict[str, Node] = {}
        edges: dict[tuple[str, str, str], Edge] = {}
        rows: dict[str, tuple[str, Any]] = {}
        root = self._node(type_name, root_rows[0])
        nodes[root.id] = root
        rows[root.id] = (type_name, root_rows[0])
        frontier = [root.id]

        for _hop in range(depth):
            next_frontier: list[str] = []
            for node_id in frontier:
                t, row = rows[node_id]
                for target_type, target_row, edge_type, edge_label, outbound in await self._neighbours(t, row):
                    node = self._node(target_type, target_row)
                    if node.id not in nodes:
                        if len(nodes) >= self.max_nodes:
                            raise GraphTooLarge(
                                f"More than {self.max_nodes} nodes within depth {depth} of {type_name} {root_id}; "
                                "reduce depth or start from a narrower entity.",
                                max_nodes=self.max_nodes, depth=depth,
                            )
                        nodes[node.id] = node
                        rows[node.id] = (target_type, target_row)
                        next_frontier.append(node.id)
                    a, b = (node_id, node.id) if outbound else (node.id, node_id)
                    key = tuple(sorted((a, b))) + (edge_type,)
                    edges.setdefault(key, Edge(a, b, edge_type, edge_label))
            frontier = next_frontier
            if not frontier:
                break

        return {"nodes": [n.__dict__ for n in nodes.values()], "edges": [e.as_json() for e in edges.values()]}
