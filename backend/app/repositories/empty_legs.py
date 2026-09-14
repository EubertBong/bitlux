"""Empty legs: the customer-facing search."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from sqlalchemy.orm import aliased

from app.models import AircraftModel, Airport, EmptyLeg
from app.models.enums import AircraftCategory, EmptyLegStatus

from .base import BaseRepository

__all__ = ["EmptyLegRepository"]


def _start(d: date | datetime) -> datetime:
    return d if isinstance(d, datetime) else datetime.combine(d, time.min, tzinfo=timezone.utc)


def _end(d: date | datetime) -> datetime:
    return d if isinstance(d, datetime) else datetime.combine(d, time.max, tzinfo=timezone.utc)


class EmptyLegRepository(BaseRepository[EmptyLeg]):
    model = EmptyLeg

    async def search(
        self,
        origin: str | uuid.UUID,
        destination: str | uuid.UUID,
        date_from: date | datetime,
        date_to: date | datetime,
        cabin_class: AircraftCategory | None = None,
        limit: int = 50,
    ) -> list[EmptyLeg]:
        """Available empty legs on a route whose departure window overlaps the dates.

        ``origin``/``destination`` are ICAO/IATA codes or airport ids.
        ``cabin_class`` filters on the offered type's category (uses
        ``ix_empty_legs_route``, which is partial on status = 'available').
        """
        dep, arr = aliased(Airport), aliased(Airport)
        stmt = (
            self._base_query()
            .join(dep, dep.id == EmptyLeg.departure_airport_id)
            .join(arr, arr.id == EmptyLeg.arrival_airport_id)
            .where(
                EmptyLeg.status == EmptyLegStatus.AVAILABLE,
                self._airport_match(dep, origin),
                self._airport_match(arr, destination),
                EmptyLeg.earliest_departure_at <= _end(date_to),
                EmptyLeg.latest_departure_at >= _start(date_from),
            )
        )
        if cabin_class is not None:
            stmt = stmt.join(AircraftModel, AircraftModel.id == EmptyLeg.aircraft_model_id).where(AircraftModel.category == cabin_class)
        stmt = stmt.order_by(EmptyLeg.earliest_departure_at, EmptyLeg.asking_price_cents).limit(limit)
        return list((await self.session.execute(stmt)).scalars().all())

    @staticmethod
    def _airport_match(alias, ref: str | uuid.UUID):
        if isinstance(ref, uuid.UUID):
            return alias.id == ref
        code = ref.strip().upper()
        return (alias.icao_code == code) | (alias.iata_code == code)

    async def for_operator(self, operator_id: uuid.UUID) -> list[EmptyLeg]:
        return await self.list(operator_id=operator_id, order_by=(EmptyLeg.earliest_departure_at,))

    async def expired(self, as_of: datetime | None = None) -> list[EmptyLeg]:
        """Still marked available but past expires_at -- the sweep marks these expired."""
        as_of = as_of or datetime.now(timezone.utc)
        return await self.list(EmptyLeg.status == EmptyLegStatus.AVAILABLE, EmptyLeg.expires_at < as_of, order_by=(EmptyLeg.expires_at,))
