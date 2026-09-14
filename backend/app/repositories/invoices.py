"""Invoices and accounts-receivable reporting."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import case, func, select

from app.models import Invoice
from app.models.enums import InvoiceStatus

from .base import BaseRepository

__all__ = ["InvoiceRepository", "AgingBucket", "AgingReport", "UNSETTLED", "AGING_BUCKETS"]

# Statuses that still owe money.
UNSETTLED = (InvoiceStatus.ISSUED, InvoiceStatus.SENT, InvoiceStatus.PARTIALLY_PAID, InvoiceStatus.OVERDUE)
AGING_BUCKETS = ("current", "1-30", "31-60", "61-90", "90+")


@dataclass(frozen=True)
class AgingBucket:
    bucket: str
    count: int = 0
    balance_cents: int = 0


@dataclass
class AgingReport:
    as_of: date
    buckets: dict[str, AgingBucket] = field(default_factory=dict)

    @property
    def total_cents(self) -> int:
        return sum(b.balance_cents for b in self.buckets.values())

    @property
    def overdue_cents(self) -> int:
        return sum(b.balance_cents for k, b in self.buckets.items() if k != "current")


class InvoiceRepository(BaseRepository[Invoice]):
    model = Invoice

    async def by_number(self, invoice_number: str):
        return (await self.session.execute(self._base_query().where(Invoice.invoice_number == invoice_number))).scalar_one_or_none()

    async def for_account_holder(self, account_holder_id: uuid.UUID, **page: int) -> list[Invoice]:
        return await self.list(account_holder_id=account_holder_id, order_by=(Invoice.issue_date.desc().nulls_last(),), **page)

    async def unsettled(self, **page: int) -> list[Invoice]:
        return await self.list(Invoice.status.in_(UNSETTLED), order_by=(Invoice.due_date.nulls_last(),), **page)

    async def overdue(self, as_of: date | None = None, **page: int) -> list[Invoice]:
        """Unsettled and past due. Uses due_date, not the 'overdue' status, so a
        stale status cannot hide an invoice."""
        as_of = as_of or date.today()
        return await self.list(Invoice.status.in_(UNSETTLED), Invoice.due_date < as_of, order_by=(Invoice.due_date,), **page)

    async def ar_aging(self, as_of: date | None = None) -> AgingReport:
        """Outstanding balance bucketed by days past due: current / 1-30 / 31-60 / 61-90 / 90+.

        A NULL due_date counts as current. Balance is the generated
        ``balance_cents`` (total - amount_paid), so a partially paid invoice
        contributes only what is still owed.
        """
        as_of = as_of or date.today()
        days_late = func.cast(as_of, Invoice.due_date.type) - Invoice.due_date  # date - date -> integer days
        bucket = case(
            (Invoice.due_date.is_(None), "current"),
            (Invoice.due_date >= as_of, "current"),
            (days_late <= 30, "1-30"),
            (days_late <= 60, "31-60"),
            (days_late <= 90, "61-90"),
            else_="90+",
        ).label("bucket")
        stmt = (
            select(bucket, func.count().label("n"), func.coalesce(func.sum(Invoice.balance_cents), 0).label("balance"))
            .where(self._live_predicate(), self._tenant_predicate(), Invoice.status.in_(UNSETTLED), Invoice.balance_cents > 0)
            .group_by(bucket)
        )
        rows = (await self.session.execute(stmt)).all()
        report = AgingReport(as_of=as_of, buckets={b: AgingBucket(b) for b in AGING_BUCKETS})
        for r in rows:
            report.buckets[r.bucket] = AgingBucket(r.bucket, int(r.n), int(r.balance))
        return report
