"""The audit trail: append-only, and the repository is the only writer.

``append()`` inserts through SQLAlchemy Core -- no ``AuditLog`` instance is ever
constructed (the model's ``__init__`` raises). Every other write on the base
class is refused via ``immutable = True``; the model's ORM event listeners and
the database trigger (migration 013) back that up.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import insert

from app.models import AuditLog
from app.models.base import utcnow, uuid7
from app.models.enums import ActorType, AuditAction, EntityType

from .base import BaseRepository
from .context import current_actor_type, current_client_id_or_none, current_user_id

__all__ = ["AuditEvent", "AuditLogRepository"]


@dataclass
class AuditEvent:
    """What happened. Anything not given is stamped from the tenant context."""

    action: AuditAction
    entity_type: EntityType
    actor_label: str
    entity_id: Optional[uuid.UUID] = None
    entity_label: Optional[str] = None
    changed_fields: Optional[list[str]] = None
    before: Optional[dict[str, Any]] = None
    after: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    request_id: Optional[uuid.UUID] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    occurred_at: Optional[datetime] = None
    actor_type: Optional[ActorType] = None
    actor_user_id: Optional[uuid.UUID] = None
    impersonated_by_user_id: Optional[uuid.UUID] = None
    api_key_id: Optional[uuid.UUID] = None
    client_id: Optional[uuid.UUID] = field(default=None, repr=False)


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog
    immutable = True  # create/update/soft_delete/restore/hard_delete all raise ImmutableModel

    async def append(self, event: AuditEvent | dict[str, Any]) -> uuid.UUID:
        """The ONLY write path. Returns the new row's id.

        Callers are responsible for redacting [enc] fields out of ``before`` /
        ``after`` -- an audit trail that logs plaintext passport numbers defeats
        the encryption (DATA_MODEL 5, "Encryption boundary").
        """
        row = asdict(event) if isinstance(event, AuditEvent) else dict(event)
        row.setdefault("id", uuid7())
        row["occurred_at"] = row.get("occurred_at") or utcnow()
        if row.get("client_id") is None:
            row["client_id"] = current_client_id_or_none()
        if row.get("actor_type") is None:
            row["actor_type"] = current_actor_type()
        if row.get("actor_user_id") is None:
            row["actor_user_id"] = current_user_id()
        row = {k: v for k, v in row.items() if k in AuditLog.__table__.c}
        await self.session.execute(insert(AuditLog.__table__).values(**row))
        return row["id"]

    async def history_of(self, entity_type: EntityType, entity_id: uuid.UUID, **page: int) -> list[AuditLog]:
        """Everything that ever happened to one record, newest first."""
        return await self.list(entity_type=entity_type, entity_id=entity_id, order_by=(AuditLog.occurred_at.desc(),), **page)

    async def by_actor(self, user_id: uuid.UUID, **page: int) -> list[AuditLog]:
        return await self.list(actor_user_id=user_id, order_by=(AuditLog.occurred_at.desc(),), **page)
