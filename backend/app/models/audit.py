"""Append-only audit trail (DATA_MODEL.md 3.9)."""

import uuid
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import event, Column, ForeignKey, Index, text, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import ARRAY, INET, JSONB, UUID
from sqlmodel import Field

from .base import BitluxBase, OptionalTenantColumnMixin, pg_enum, utcnow, uuid7
from .enums import ActorType, AuditAction, EntityType


class AuditLog(BitluxBase, OptionalTenantColumnMixin, table=True):
    """Append-only audit trail, monthly partitions (DATA_MODEL.md 3.9).

    The table comment below is the one migration 012 leaves in place via COMMENT ON,
    which is what autogenerate compares against.
    """
    __tablename__ = "audit_logs"
    __table_args__ = (
        Index("ix_audit_logs_entity", "client_id", "entity_type", "entity_id", text("occurred_at DESC")),
        Index("ix_audit_logs_actor", "client_id", "actor_user_id", text("occurred_at DESC")),
        Index("ix_audit_logs_action", "client_id", "action", text("occurred_at DESC")),
        Index("ix_audit_logs_occurred_brin", "occurred_at", postgresql_using="brin"),
        Index("ix_audit_logs_after_gin", "after", postgresql_using="gin", postgresql_ops={"after": "jsonb_path_ops"}),
        # Migration 012 sets this comment twice (create_table, then COMMENT ON); this is
        # the second, final value, which is what autogenerate compares against.
        {"comment": "Append-only. The application role holds SELECT, INSERT only (migration 012, asserted in 015); UPDATE/DELETE are additionally blocked for every role, owner included, by trigger trg_audit_logs_immutable (migration 013).", "postgresql_partition_by": "RANGE (occurred_at)"},
    )

    id: uuid.UUID = Field(default_factory=uuid7, sa_column=Column("id", UUID(as_uuid=True), primary_key=True))
    occurred_at: datetime = Field(default_factory=utcnow, sa_column=Column("occurred_at", TIMESTAMP(timezone=True), primary_key=True, server_default=text("now()")))
    created_at: datetime = Field(default_factory=utcnow, sa_column=Column("created_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")))
    action: AuditAction = Field(sa_column=Column("action", pg_enum(AuditAction), nullable=False))
    entity_type: EntityType = Field(sa_column=Column("entity_type", pg_enum(EntityType), nullable=False))
    entity_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("entity_id", UUID(as_uuid=True)))
    entity_label: Optional[str] = Field(default=None, sa_column=Column("entity_label", Text))
    actor_type: ActorType = Field(default=ActorType.USER, sa_column=Column("actor_type", pg_enum(ActorType), nullable=False, server_default="user"))
    actor_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("actor_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    actor_label: str = Field(sa_column=Column("actor_label", Text, nullable=False))
    impersonated_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("impersonated_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    api_key_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("api_key_id", UUID(as_uuid=True)))
    changed_fields: Optional[list[str]] = Field(default=None, sa_column=Column("changed_fields", ARRAY(Text)))
    before: Optional[dict[str, Any]] = Field(default=None, sa_column=Column("before", JSONB))
    after: Optional[dict[str, Any]] = Field(default=None, sa_column=Column("after", JSONB))
    reason: Optional[str] = Field(default=None, sa_column=Column("reason", Text))
    request_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("request_id", UUID(as_uuid=True)))
    session_id: Optional[str] = Field(default=None, sa_column=Column("session_id", Text))
    ip_address: Optional[Any] = Field(default=None, sa_column=Column("ip_address", INET))
    user_agent: Optional[str] = Field(default=None, sa_column=Column("user_agent", Text))

    # ------------------------------------------------------------------ read-only
    # There is no ORM save path for audit rows. Construction raises; the only writer is
    # AuditLogRepository.append(), which inserts through SQLAlchemy Core and never
    # instantiates this class. Rows loaded from the database bypass __init__, so reads
    # work normally.
    def __init__(self, **data: object) -> None:  # noqa: D401
        raise TypeError(
            "AuditLog is append-only and cannot be constructed via the ORM save path; "
            "use AuditLogRepository.append()."
        )


def _forbid_mutation(mapper: object, connection: object, target: AuditLog) -> None:
    # Belt to the database's braces: migration 013's trigger raises too, but failing in
    # Python keeps the error next to the code that made the mistake.
    raise PermissionError(f"audit_logs is append-only; refusing to modify {target!r}")


event.listen(AuditLog, "before_update", _forbid_mutation)
event.listen(AuditLog, "before_delete", _forbid_mutation)
