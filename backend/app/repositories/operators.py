"""Operators and their safety ratings."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

from sqlalchemy import select

from app.models import Operator, OperatorSafetyRating
from app.models.enums import OperatorStatus

from .base import BaseRepository

__all__ = ["OperatorRepository", "OperatorSafetyRatingRepository"]


class OperatorSafetyRatingRepository(BaseRepository[OperatorSafetyRating]):
    model = OperatorSafetyRating

    async def current_for(self, operator_id: uuid.UUID) -> list[OperatorSafetyRating]:
        return await self.list(operator_id=operator_id, is_current=True, order_by=(OperatorSafetyRating.program,))


class OperatorRepository(BaseRepository[Operator]):
    model = Operator

    async def approved(self, **page: int) -> list[Operator]:
        return await self.list(Operator.status.in_((OperatorStatus.APPROVED, OperatorStatus.CONDITIONAL)), order_by=(Operator.is_preferred.desc(), Operator.legal_name), **page)

    async def with_lapsed_rating(self, as_of: date | None = None) -> list[Operator]:
        """Operators whose *current* rating on any program has expired.

        Current-but-expired is the dangerous state: the badge is still on the
        profile, the audit behind it is not. Renewed ratings replace the current
        row, so a superseded old rating does not count.
        """
        as_of = as_of or date.today()
        stmt = (
            self._base_query()
            .join(OperatorSafetyRating, OperatorSafetyRating.operator_id == Operator.id)
            .where(
                OperatorSafetyRating.is_current.is_(True),
                OperatorSafetyRating.deleted_at.is_(None),
                OperatorSafetyRating.expiry_date < as_of,
            )
            .order_by(Operator.legal_name)
            .distinct()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def insurance_expiring_within(self, days: int, as_of: date | None = None) -> list[Operator]:
        as_of = as_of or date.today()
        return await self.list(Operator.insurance_expiry.between(as_of, as_of + timedelta(days=days)), order_by=(Operator.insurance_expiry,))

    async def aoc_expiring_within(self, days: int, as_of: date | None = None) -> list[Operator]:
        as_of = as_of or date.today()
        return await self.list(Operator.aoc_expiry.between(as_of, as_of + timedelta(days=days)), order_by=(Operator.aoc_expiry,))
