"""Quotes -- immutable revisions -- and their line items."""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select

from app.models import Quote, QuoteLineItem
from app.models.enums import QuoteStatus

from .base import BaseRepository, RepositoryError
from .context import current_user_id

__all__ = ["QuoteRepository", "QuoteLineItemRepository"]

# Columns that never carry over to a new revision: identity, audit stamps, the
# revision chain itself, and everything that records what happened to the *old*
# revision (it was sent, viewed, accepted -- the new one has not been).
_NOT_COPIED = {
    "id", "created_at", "updated_at", "deleted_at", "created_by", "updated_by",
    "revision", "parent_quote_id", "is_current", "status", "margin_cents",
    "sent_at", "first_viewed_at", "last_viewed_at", "view_count",
    "accepted_at", "declined_at", "decline_reason", "pdf_document_id", "esign_envelope_id",
}
_LINE_NOT_COPIED = {"id", "quote_id", "created_at", "updated_at", "deleted_at", "created_by", "updated_by"}


class QuoteLineItemRepository(BaseRepository[QuoteLineItem]):
    model = QuoteLineItem

    async def for_quote(self, quote_id: uuid.UUID) -> list[QuoteLineItem]:
        return await self.list(quote_id=quote_id, order_by=(QuoteLineItem.sort_order,), page_size=500)


class QuoteRepository(BaseRepository[Quote]):
    model = Quote

    async def current_for_trip(self, trip_id: uuid.UUID) -> list[Quote]:
        """The live revision of every quote on a trip (usually one)."""
        return await self.list(trip_id=trip_id, is_current=True, order_by=(Quote.created_at,))

    async def revisions(self, quote_number: str) -> list[Quote]:
        """Full history of one quote number, oldest first."""
        return await self.list(quote_number=quote_number, order_by=(Quote.revision,), page_size=500)

    async def supersede(
        self,
        quote_id: uuid.UUID,
        new_data: dict[str, Any],
        line_items: Optional[list[dict[str, Any]]] = None,
    ) -> Quote:
        """Create revision N+1 from revision N (DATA_MODEL 5, "Quote versioning").

        A sent quote is never edited. This copies the current revision, overlays
        ``new_data``, links it back via ``parent_quote_id``, and retires the old
        one (``is_current = false``, ``status = superseded``). Line items are
        copied unless ``line_items`` is given, in which case those replace them.

        Order matters: the partial unique index ``uq_quotes_current`` allows one
        live revision per quote number, so the old row is retired and flushed
        *before* the new one is inserted.
        """
        old = await self.get_or_raise(quote_id)
        if not old.is_current:
            raise RepositoryError(f"quote {old.quote_number} r{old.revision} is not the current revision")
        if old.status == QuoteStatus.ACCEPTED:
            raise RepositoryError("an accepted quote cannot be superseded; issue a new quote instead")
        for key in ("revision", "parent_quote_id", "is_current", "quote_number"):
            if key in new_data:
                raise RepositoryError(f"{key} is managed by supersede()")

        old_items = await QuoteLineItemRepository(self.session).for_quote(old.id)

        old.is_current = False
        old.status = QuoteStatus.SUPERSEDED
        old.updated_by = current_user_id()
        await self.session.flush()

        data = {c.name: getattr(old, c.name) for c in Quote.__table__.c if c.name not in _NOT_COPIED}
        data.update(new_data)
        data.update(revision=old.revision + 1, parent_quote_id=old.id, is_current=True, status=QuoteStatus.DRAFT)
        new = await self.create(data)

        items = line_items if line_items is not None else [
            {c.name: getattr(li, c.name) for c in QuoteLineItem.__table__.c if c.name not in _LINE_NOT_COPIED}
            for li in old_items
        ]
        lines = QuoteLineItemRepository(self.session)
        for item in items:
            await lines.create({**item, "quote_id": new.id})
        return new
