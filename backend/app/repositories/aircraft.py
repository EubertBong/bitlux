"""Aircraft, models and manufacturers -- including the two questions ops asks at 3am."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import exists, select

from app.models import Aircraft, AircraftModel, Leg, Manufacturer
from app.models.enums import AircraftStatus, LegStatus

from .base import BaseRepository, SharedCatalogRepository

__all__ = ["AircraftRepository", "AircraftModelRepository", "ManufacturerRepository"]


class ManufacturerRepository(SharedCatalogRepository[Manufacturer]):
    model = Manufacturer


class AircraftModelRepository(SharedCatalogRepository[AircraftModel]):
    model = AircraftModel

    async def by_name(self, name: str) -> Optional[AircraftModel]:
        return (await self.session.execute(self._base_query().where(AircraftModel.name.ilike(name)))).scalar_one_or_none()

    async def by_icao(self, icao_type_code: str) -> list[AircraftModel]:
        return await self.list(icao_type_code=icao_type_code.upper())


class AircraftRepository(BaseRepository[Aircraft]):
    model = Aircraft

    async def by_tail(self, tail_number: str) -> Optional[Aircraft]:
        # tail_number is citext: equality is case-insensitive.
        return (await self.session.execute(self._base_query().where(Aircraft.tail_number == tail_number))).scalar_one_or_none()

    def _leg_window(self, aircraft_id: uuid.UUID, start: datetime, end: datetime):
        return (
            Leg.aircraft_id == aircraft_id,
            Leg.deleted_at.is_(None),
            Leg.status != LegStatus.CANCELLED,
            Leg.scheduled_departure_at < end,
            Leg.scheduled_arrival_at > start,
        )

    async def legs_at(self, aircraft_id: uuid.UUID, at: datetime) -> list[Leg]:
        """Every live leg this tail is scheduled to be flying at one instant."""
        stmt = select(Leg).where(*self._leg_window(aircraft_id, at, at), Leg.scheduled_departure_at <= at).order_by(Leg.scheduled_departure_at)
        # _leg_window with start == end degenerates to dep < at AND arr > at; the extra
        # predicate makes the departure boundary inclusive.
        stmt = select(Leg).where(
            Leg.aircraft_id == aircraft_id, Leg.deleted_at.is_(None), Leg.status != LegStatus.CANCELLED,
            Leg.scheduled_departure_at <= at, Leg.scheduled_arrival_at > at,
        ).order_by(Leg.scheduled_departure_at)
        return list((await self.session.execute(stmt)).scalars().all())

    async def double_booked(self, aircraft_id: uuid.UUID, at: datetime) -> list[Leg]:
        """The conflicting legs if the tail is committed to more than one at ``at``; else []."""
        legs = await self.legs_at(aircraft_id, at)
        return legs if len(legs) > 1 else []

    async def conflicting_legs(
        self, aircraft_id: uuid.UUID, start: datetime, end: datetime, exclude_leg_id: uuid.UUID | None = None
    ) -> list[Leg]:
        """Legs that overlap a proposed [start, end) window -- run before assigning a tail."""
        stmt = select(Leg).where(*self._leg_window(aircraft_id, start, end))
        if exclude_leg_id is not None:
            stmt = stmt.where(Leg.id != exclude_leg_id)
        return list((await self.session.execute(stmt.order_by(Leg.scheduled_departure_at))).scalars().all())

    async def available_between(self, aircraft_model_id: uuid.UUID, start: datetime, end: datetime) -> list[Aircraft]:
        """Active, charter-available tails of a type with no leg overlapping the window."""
        busy = exists().where(*self._leg_window(Aircraft.id, start, end))  # correlated on Aircraft.id
        stmt = (
            self._base_query()
            .where(
                Aircraft.aircraft_model_id == aircraft_model_id,
                Aircraft.status == AircraftStatus.ACTIVE,
                Aircraft.is_available_for_charter.is_(True),
                ~busy,
            )
            .order_by(Aircraft.tail_number)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def for_operator(self, operator_id: uuid.UUID) -> list[Aircraft]:
        return await self.list(operator_id=operator_id, order_by=(Aircraft.tail_number,))
