"""Cross-entity full-text search on the generated tsvector columns.

Every type below is served by a GIN index (migrations 003-011, 016); nothing
here uses ILIKE. User input goes through ``websearch_to_tsquery`` (quotes, AND,
OR, -negation) and is additionally OR-ed with a prefix query on the last word so
that a half-typed "gulf" finds "Gulfstream".

Why the query goes through ``search_ids()`` (migration 017) and not a plain
``WHERE search_tsv @@ query``: under Row-Level Security the planner will not use
a non-LEAKPROOF operator -- and ``@@`` is one -- as an index condition beneath the
policy qual, so for the app role the direct form is always a sequential scan.
``search_ids`` is SECURITY DEFINER with ``row_security = off``, tenant-scoped by
the same ``current_client_id()`` the policies use, static SQL only, and returns
just ``(id, rank)``; the ids are then joined from a statement that is itself
still under RLS, so nothing is returned that the policy would not allow.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from sqlalchemy import Float, Integer, Text, column, func, literal
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Aircraft, AircraftModel, Airport, Contact, Document, Manufacturer, Operator, Passenger, Quote, Trip

from .aircraft import AircraftModelRepository, AircraftRepository, ManufacturerRepository
from .airports import AirportRepository
from .contacts import ContactRepository
from .documents import DocumentRepository
from .operators import OperatorRepository
from .passengers import PassengerRepository
from .quotes import QuoteRepository
from .trips import TripRepository

__all__ = ["SearchHit", "SearchRepository", "SEARCH_TYPES"]


@dataclass(frozen=True)
class SearchHit:
    id: uuid.UUID
    type: str
    label: str
    subtitle: Optional[str]
    url: str
    rank: float


@dataclass(frozen=True)
class _Type:
    repo: type
    model: type
    tsv: Callable[[], object]        # the indexed tsvector expression
    config: str                      # 'english' for prose, 'simple' for identifiers
    label: Callable[[object], str]
    subtitle: Callable[[object], Optional[str]]
    permission: str
    url: str


def _num(expr):  # the 016 expression indexes: to_tsvector('simple', col::text)
    return func.to_tsvector("simple", func.cast(expr, Text))


SEARCH_TYPES: dict[str, _Type] = {
    "contacts": _Type(ContactRepository, Contact, lambda: Contact.search_tsv, "english",
                      lambda r: r.display_name, lambda r: r.job_title or r.company_name or r.primary_email, "contacts.view", "/contacts"),
    "passengers": _Type(PassengerRepository, Passenger, lambda: Passenger.search_tsv, "english",
                        lambda r: f"{r.first_name} {r.last_name}", lambda r: r.nationality_code, "passengers.view", "/passengers"),
    "operators": _Type(OperatorRepository, Operator, lambda: Operator.search_tsv, "english",
                       lambda r: r.dba_name or r.legal_name, lambda r: f"{r.status.value} · {r.country_code or ''}".strip(" ·"), "operators.view", "/operators"),
    "aircraft": _Type(AircraftRepository, Aircraft, lambda: Aircraft.search_tsv, "english",
                      lambda r: r.tail_number, lambda r: r.status.value, "aircraft.view", "/aircraft"),
    "airports": _Type(AirportRepository, Airport, lambda: Airport.search_tsv, "english",
                      lambda r: f"{r.icao_code or r.iata_code or ''} {r.name}".strip(), lambda r: r.city, "airports.view", "/airports"),
    "manufacturers": _Type(ManufacturerRepository, Manufacturer, lambda: Manufacturer.search_tsv, "english",
                           lambda r: r.name, lambda r: r.country_code, "manufacturers.view", "/manufacturers"),
    "aircraft_models": _Type(AircraftModelRepository, AircraftModel, lambda: AircraftModel.search_tsv, "english",
                             lambda r: r.name, lambda r: r.category.value.replace("_", " "), "aircraft_models.view", "/aircraft_models"),
    "trips": _Type(TripRepository, Trip, lambda: _num(Trip.trip_number), "simple",
                   lambda r: r.trip_number, lambda r: f"{r.status.value} · {r.departure_date or ''}".strip(" ·"), "trips.view", "/trips"),
    "quotes": _Type(QuoteRepository, Quote, lambda: _num(Quote.quote_number), "simple",
                    lambda r: f"{r.quote_number} r{r.revision}", lambda r: r.status.value, "quotes.view", "/quotes"),
    # documents.ocr_tsv is the indexed column; it covers title + description (+ OCR text).
    "documents": _Type(DocumentRepository, Document, lambda: Document.ocr_tsv, "english",
                       lambda r: r.title, lambda r: r.document_type.value.replace("_", " "), "documents.view", "/documents"),
}

_WORD = re.compile(r"[A-Za-z0-9]+")


def _tsquery(q: str, config: str):
    """websearch_to_tsquery(q) OR prefix(last word). The prefix half is what makes
    incremental typing work; websearch alone has no prefix operator."""
    base = func.websearch_to_tsquery(config, q)
    words = _WORD.findall(q)
    if not words or q.rstrip().endswith('"'):
        return base
    prefix = func.to_tsquery(config, literal(words[-1].lower() + ":*"))
    return base.op("||")(prefix)


class SearchRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, q: str, types: list[str] | None = None, limit: int = 5) -> dict[str, list[SearchHit]]:
        """Grouped hits, best rank first within each type.

        ``search_ids()`` does the indexed match and returns ids; the join back
        through the type's repository ``_base_query()`` re-applies soft delete
        and the tenant predicate under RLS.
        """
        q = q.strip()
        if not q:
            return {}
        wanted = [t for t in (types or list(SEARCH_TYPES)) if t in SEARCH_TYPES]
        out: dict[str, list[SearchHit]] = {}
        for name in wanted:
            spec = SEARCH_TYPES[name]
            rows = (await self.session.execute(self.statement_for(q, name, limit))).all()
            hits = [SearchHit(row[0].id, name, spec.label(row[0]), spec.subtitle(row[0]), f"{spec.url}/{row[0].id}", float(row[1])) for row in rows]
            if hits:
                out[name] = hits
        return out

    def statement_for(self, q: str, type_name: str, limit: int = 5):
        """The SELECT for one type: model rows joined to search_ids(type, tsquery, limit)."""
        spec = SEARCH_TYPES[type_name]
        tsq = _tsquery(q, spec.config)
        hit = (
            func.search_ids(literal(type_name), tsq, literal(limit, Integer))
            .table_valued(column("id", UUID(as_uuid=True)), column("rank", Float))
            .render_derived()
            .alias("hit")
        )
        return (
            spec.repo(self.session)._base_query()
            .join(hit, spec.model.id == hit.c.id)
            .add_columns(hit.c.rank.label("rank"))
            .order_by(hit.c.rank.desc(), spec.model.id)
        )
