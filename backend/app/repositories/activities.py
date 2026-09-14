"""Activities: the human-facing interaction log (not the audit trail)."""

from __future__ import annotations

import uuid
from typing import Any

from app.models import Activity
from app.models.enums import ActivityDirection, ActivityType, EntityType

from .base import BaseRepository

__all__ = ["ActivityRepository"]


class ActivityRepository(BaseRepository[Activity]):
    model = Activity

    async def for_contact(self, contact_id: uuid.UUID, limit: int = 50) -> list[Activity]:
        return await self.list(contact_id=contact_id, order_by=(Activity.occurred_at.desc(),), page_size=limit)

    async def for_entity(self, entity_type: EntityType, entity_id: uuid.UUID, limit: int = 50) -> list[Activity]:
        return await self.list(entity_type=entity_type, entity_id=entity_id, order_by=(Activity.occurred_at.desc(),), page_size=limit)

    async def log(
        self,
        activity_type: ActivityType,
        subject: str,
        *,
        contact_id: uuid.UUID | None = None,
        direction: ActivityDirection = ActivityDirection.OUTBOUND,
        body: str | None = None,
        entity_type: EntityType | None = None,
        entity_id: uuid.UUID | None = None,
        **extra: Any,
    ) -> Activity:
        """Convenience for the common case; user_id defaults to the acting user."""
        from .context import current_user_id

        return await self.create({
            "activity_type": activity_type, "subject": subject, "contact_id": contact_id, "direction": direction,
            "body": body, "entity_type": entity_type, "entity_id": entity_id,
            "user_id": extra.pop("user_id", current_user_id()), **extra,
        })
