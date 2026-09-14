"""Crew members: currency and availability."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import select

from app.models import CrewMember, LegCrew
from app.models.enums import CrewStatus

from .base import BaseRepository

__all__ = ["CrewMemberRepository"]


class CrewMemberRepository(BaseRepository[CrewMember]):
    model = CrewMember

    async def with_type_rating(self, icao_type_code: str, active_only: bool = True) -> list[CrewMember]:
        """"Who is current on GLF6?" -- GIN-indexed array containment."""
        criteria = [CrewMember.type_ratings.contains([icao_type_code.upper()])]
        if active_only:
            criteria.append(CrewMember.status == CrewStatus.ACTIVE)
        return await self.list(*criteria, order_by=(CrewMember.last_name,))

    async def medical_expiring_within(self, days: int, as_of: date | None = None) -> list[CrewMember]:
        as_of = as_of or date.today()
        return await self.list(
            CrewMember.status == CrewStatus.ACTIVE,
            CrewMember.medical_expiry.between(as_of, as_of + timedelta(days=days)),
            order_by=(CrewMember.medical_expiry,),
        )

    async def duty_conflicts(self, crew_member_id: uuid.UUID, start: datetime, end: datetime) -> list[LegCrew]:
        """Existing duty windows overlapping a proposed one."""
        stmt = (
            select(LegCrew)
            .where(
                LegCrew.crew_member_id == crew_member_id,
                LegCrew.deleted_at.is_(None),
                LegCrew.duty_start_at < end,
                LegCrew.duty_end_at > start,
            )
            .order_by(LegCrew.duty_start_at)
        )
        return list((await self.session.execute(stmt)).scalars().all())
