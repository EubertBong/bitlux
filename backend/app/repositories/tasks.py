"""Tasks: the work queue."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models import Task
from app.models.base import utcnow
from app.models.enums import TaskStatus

from .base import BaseRepository

__all__ = ["TaskRepository", "ACTIONABLE", "OPEN_LIKE"]

ACTIONABLE = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS)
OPEN_LIKE = (TaskStatus.OPEN, TaskStatus.IN_PROGRESS, TaskStatus.BLOCKED)


class TaskRepository(BaseRepository[Task]):
    model = Task

    async def my_queue(self, user_id: uuid.UUID, **page: int) -> list[Task]:
        """What one person should look at next.

        Actionable (open / in progress), most urgent first, then soonest due.
        ``priority`` is a PostgreSQL enum declared low < normal < high < urgent,
        so ordering the column DESC is the correct priority order with no CASE.
        """
        return await self.list(
            Task.status.in_(ACTIONABLE),
            assigned_to_user_id=user_id,
            order_by=(Task.priority.desc(), Task.due_at.asc().nulls_last(), Task.created_at),
            **page,
        )

    async def overdue(self, as_of: datetime | None = None, **page: int) -> list[Task]:
        """Past due and not finished -- blocked tasks included; they are still late."""
        return await self.list(
            Task.status.in_(OPEN_LIKE),
            Task.due_at < (as_of or utcnow()),
            order_by=(Task.due_at,),
            **page,
        )

    async def for_entity(self, entity_type, entity_id: uuid.UUID, **page: int) -> list[Task]:
        return await self.list(entity_type=entity_type, entity_id=entity_id, order_by=(Task.due_at.nulls_last(),), **page)

    async def complete(self, task_id: uuid.UUID, completed_by: uuid.UUID | None = None) -> Task:
        from .context import current_user_id

        return await self.update(task_id, {
            "status": TaskStatus.COMPLETED,
            "completed_at": utcnow(),
            "completed_by_user_id": completed_by or current_user_id(),
        })
