"""The tenant root. Its "tenant predicate" is its own id."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ColumnElement

from app.models import Client

from .base import BaseRepository
from .context import current_client_id

__all__ = ["ClientRepository"]


class ClientRepository(BaseRepository[Client]):
    model = Client

    def _tenant_predicate(self) -> ColumnElement[bool]:
        # clients has no client_id column; the row *is* the tenant (DATA_MODEL 3.1).
        return Client.id == current_client_id()

    async def current(self) -> Optional[Client]:
        """The tenant this transaction is running as."""
        return await self.get(current_client_id())
