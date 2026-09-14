"""Trips and legs."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import and_, or_
from sqlalchemy.orm import selectinload

from app.models import Leg, LegCrew, LegPassenger, Trip
from app.models.enums import LegStatus, TripStatus

from .base import BaseRepository

__all__ = ["TripRepository", "LegRepository", "LegPassengerRepository", "LegCrewRepository"]


class TripRepository(BaseRepository[Trip]):
    model = Trip

    async def by_number(self, trip_number: str) -> Optional[Trip]:
        return (await self.session.execute(self._base_query().where(Trip.trip_number == trip_number))).scalar_one_or_none()

    async def with_legs(self, trip_id: uuid.UUID) -> Optional[Trip]:
        """Trip with legs eagerly loaded (lazy loads are not available under asyncio)."""
        stmt = self._base_query().where(Trip.id == trip_id).options(selectinload(Trip.legs))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def by_status(self, *statuses: TripStatus, **page: int) -> list[Trip]:
        return await self.list(Trip.status.in_(statuses), order_by=(Trip.departure_date.nulls_last(), Trip.trip_number), **page)

    async def by_date_range(self, date_from: date, date_to: date, **page: int) -> list[Trip]:
        """Trips whose [departure_date, return_date] overlaps the range (inclusive)."""
        return await self.list(
            Trip.departure_date <= date_to,
            or_(Trip.return_date >= date_from, and_(Trip.return_date.is_(None), Trip.departure_date >= date_from)),
            order_by=(Trip.departure_date, Trip.trip_number),
            **page,
        )

    async def with_margin_below(self, threshold_cents: int, **page: int) -> list[Trip]:
        """Priced trips whose generated margin is under the threshold (loss-makers at 0)."""
        return await self.list(
            Trip.margin_cents < threshold_cents,
            Trip.total_sell_cents > 0,
            order_by=(Trip.margin_cents,),
            **page,
        )

    async def upcoming(self, **page: int) -> list[Trip]:
        return await self.list(
            Trip.departure_date >= date.today(),
            Trip.status.in_((TripStatus.CONFIRMED, TripStatus.IN_PROGRESS)),
            order_by=(Trip.departure_date,),
            **page,
        )


class LegRepository(BaseRepository[Leg]):
    model = Leg

    async def for_trip(self, trip_id: uuid.UUID) -> list[Leg]:
        return await self.list(trip_id=trip_id, order_by=(Leg.leg_number,))

    async def in_window(self, start: datetime, end: datetime, **page: int) -> list[Leg]:
        """Live, non-cancelled legs overlapping [start, end)."""
        return await self.list(
            Leg.scheduled_departure_at < end,
            Leg.scheduled_arrival_at > start,
            Leg.status != LegStatus.CANCELLED,
            order_by=(Leg.scheduled_departure_at,),
            **page,
        )


class LegPassengerRepository(BaseRepository[LegPassenger]):
    model = LegPassenger


class LegCrewRepository(BaseRepository[LegCrew]):
    model = LegCrew
