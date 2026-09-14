"""Bookings."""

from __future__ import annotations

import uuid
from typing import Optional

from app.models import Booking
from app.models.enums import BookingStatus

from .base import BaseRepository

__all__ = ["BookingRepository"]


class BookingRepository(BaseRepository[Booking]):
    model = Booking

    async def live_for_trip(self, trip_id: uuid.UUID) -> Optional[Booking]:
        """The one non-cancelled booking a trip may have (uq_bookings_live_per_trip)."""
        stmt = self._base_query().where(Booking.trip_id == trip_id, Booking.status != BookingStatus.CANCELLED)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def by_status(self, *statuses: BookingStatus, **page: int) -> list[Booking]:
        return await self.list(Booking.status.in_(statuses), order_by=(Booking.created_at.desc(),), **page)

    async def awaiting_deposit(self) -> list[Booking]:
        return await self.list(
            Booking.deposit_required_cents > 0,
            Booking.deposit_received_at.is_(None),
            Booking.status != BookingStatus.CANCELLED,
            order_by=(Booking.deposit_due_at.nulls_last(),),
        )
