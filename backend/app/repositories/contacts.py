"""CRM spine: segments, contacts and their channels, account holders."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import func, select

from app.models import AccountHolder, AccountHolderPassenger, Contact, ContactChannel, Segment

from .base import BaseRepository

__all__ = ["SegmentRepository", "ContactRepository", "ContactChannelRepository", "AccountHolderRepository"]


class SegmentRepository(BaseRepository[Segment]):
    model = Segment

    async def by_code(self, code: str) -> Optional[Segment]:
        return (await self.session.execute(self._base_query().where(Segment.code == code))).scalar_one_or_none()

    async def roots(self) -> list[Segment]:
        return await self.list(Segment.parent_segment_id.is_(None), order_by=(Segment.sort_order, Segment.name))


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    async def by_segment(self, segment_id: uuid.UUID, **page: int) -> list[Contact]:
        return await self.list(segment_id=segment_id, order_by=(Contact.display_name,), **page)

    async def by_owner(self, user_id: uuid.UUID, **page: int) -> list[Contact]:
        return await self.list(owner_user_id=user_id, order_by=(Contact.last_activity_at.desc().nulls_last(), Contact.display_name), **page)

    async def by_email(self, email: str) -> Optional[Contact]:
        # primary_email is citext, so equality is already case-insensitive.
        return (await self.session.execute(self._base_query().where(Contact.primary_email == email))).scalar_one_or_none()

    async def search(self, term: str, limit: int = 20) -> list[Contact]:
        """Full-text search over the generated search_tsv (name, company, email, phone)."""
        stmt = (
            self._base_query()
            .where(Contact.search_tsv.op("@@")(func.plainto_tsquery("english", term)))
            .order_by(Contact.display_name)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def employees_of(self, company_contact_id: uuid.UUID) -> list[Contact]:
        return await self.list(parent_contact_id=company_contact_id, order_by=(Contact.display_name,))


class ContactChannelRepository(BaseRepository[ContactChannel]):
    model = ContactChannel

    async def for_contact(self, contact_id: uuid.UUID) -> list[ContactChannel]:
        return await self.list(contact_id=contact_id, order_by=(ContactChannel.is_primary.desc(), ContactChannel.channel_type))


class AccountHolderRepository(BaseRepository[AccountHolder]):
    model = AccountHolder

    async def by_account_number(self, number: str) -> Optional[AccountHolder]:
        return (await self.session.execute(self._base_query().where(AccountHolder.account_number == number))).scalar_one_or_none()

    async def for_passenger(self, passenger_id: uuid.UUID) -> list[AccountHolder]:
        """Accounts a passenger is authorised to fly on."""
        stmt = (
            self._base_query()
            .join(AccountHolderPassenger, AccountHolderPassenger.account_holder_id == AccountHolder.id)
            .where(AccountHolderPassenger.passenger_id == passenger_id, AccountHolderPassenger.deleted_at.is_(None))
            .order_by(AccountHolder.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def with_outstanding_balance(self) -> list[AccountHolder]:
        return await self.list(AccountHolder.balance_cents > 0, order_by=(AccountHolder.balance_cents.desc(),))
