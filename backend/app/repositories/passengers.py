"""Passengers, their travel documents, and where they have flown."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Leg, LegPassenger, Passenger, TravelDocument, Trip
from app.models.enums import TravelDocumentType

from .base import BaseRepository

__all__ = ["PassengerRepository", "TravelDocumentRepository"]


class PassengerRepository(BaseRepository[Passenger]):
    model = Passenger

    async def flown_on_leg(self, leg_id: uuid.UUID) -> list[Passenger]:
        """The manifest for one leg."""
        stmt = (
            self._base_query()
            .join(LegPassenger, LegPassenger.passenger_id == Passenger.id)
            .where(LegPassenger.leg_id == leg_id, LegPassenger.deleted_at.is_(None))
            .order_by(LegPassenger.is_lead_passenger.desc(), Passenger.last_name, Passenger.first_name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def flight_history(self, passenger_id: uuid.UUID, limit: int = 100) -> list[Leg]:
        """Every leg this passenger was manifested on, newest first."""
        stmt = (
            select(Leg)
            .join(LegPassenger, LegPassenger.leg_id == Leg.id)
            .join(Trip, Trip.id == Leg.trip_id)
            .where(
                LegPassenger.passenger_id == passenger_id,
                LegPassenger.deleted_at.is_(None),
                Leg.deleted_at.is_(None),
                Trip.deleted_at.is_(None),
                Leg.client_id == self._tenant_predicate().right,  # same tenant, explicitly
            )
            .order_by(Leg.scheduled_departure_at.desc())
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def for_contact(self, contact_id: uuid.UUID) -> list[Passenger]:
        return await self.list(contact_id=contact_id, order_by=(Passenger.last_name, Passenger.first_name))

    async def guests(self) -> list[Passenger]:
        """Passengers with no CRM contact record (DATA_MODEL 3.2)."""
        return await self.list(Passenger.contact_id.is_(None), order_by=(Passenger.last_name,))


class TravelDocumentRepository(BaseRepository[TravelDocument]):
    model = TravelDocument

    async def for_passenger(self, passenger_id: uuid.UUID) -> list[TravelDocument]:
        return await self.list(passenger_id=passenger_id, order_by=(TravelDocument.is_primary.desc(), TravelDocument.expiry_date))

    async def expiring_within(self, days: int, document_type: TravelDocumentType | None = TravelDocumentType.PASSPORT) -> list[TravelDocument]:
        """Feeds the compliance sweep -> tasks (DATA_MODEL 5). Ordered soonest first."""
        today = date.today()
        criteria = [TravelDocument.expiry_date.between(today, today + timedelta(days=days))]
        if document_type is not None:
            criteria.append(TravelDocument.document_type == document_type)
        return await self.list(*criteria, order_by=(TravelDocument.expiry_date,), page_size=500)
