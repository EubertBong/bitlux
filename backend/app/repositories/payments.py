"""Payments and refunds."""

from __future__ import annotations

import uuid
from datetime import date, datetime, time, timezone

from app.models import Payment

from .base import BaseRepository

__all__ = ["PaymentRepository"]


def _bound(d: date | datetime | None, end: bool) -> datetime | None:
    if d is None or isinstance(d, datetime):
        return d
    return datetime.combine(d, time.max if end else time.min, tzinfo=timezone.utc)


class PaymentRepository(BaseRepository[Payment]):
    model = Payment

    async def by_account_holder(
        self,
        account_holder_id: uuid.UUID,
        date_from: date | datetime | None = None,
        date_to: date | datetime | None = None,
        **page: int,
    ) -> list[Payment]:
        """Payments (and refunds, which are negative) received in a window, newest first."""
        criteria = []
        if (lo := _bound(date_from, end=False)) is not None:
            criteria.append(Payment.received_at >= lo)
        if (hi := _bound(date_to, end=True)) is not None:
            criteria.append(Payment.received_at <= hi)
        return await self.list(*criteria, account_holder_id=account_holder_id, order_by=(Payment.received_at.desc(),), **page)

    async def for_invoice(self, invoice_id: uuid.UUID) -> list[Payment]:
        return await self.list(invoice_id=invoice_id, order_by=(Payment.received_at,))

    async def refunds(self, **page: int) -> list[Payment]:
        return await self.list(Payment.refund_of_payment_id.is_not(None), order_by=(Payment.received_at.desc(),), **page)
