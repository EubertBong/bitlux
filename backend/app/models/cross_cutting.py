"""Cross-cutting: documents, tasks, activities, tags (DATA_MODEL.md 3.9). Polymorphic (entity_type, entity_id) edges are deliberately NOT relationships; see app.repositories.polymorphic."""

import uuid
from datetime import date, datetime
from typing import Any, Optional, TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, CheckConstraint, Column, Computed, Date, ForeignKey, Index, Integer, SmallInteger, text, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import CITEXT, JSONB, TSVECTOR, UUID
from sqlmodel import Field, Relationship

from .base import BitluxBase, TenantScopedMixin, pg_enum, tenant_indexes, utcnow
from .enums import ActivityDirection, ActivityType, DocumentStatus, DocumentType, EntityType, StorageProvider, TaskPriority, TaskStatus, TaskType

if TYPE_CHECKING:
    from .crm import Contact


class Document(BitluxBase, TenantScopedMixin, table=True):
    """Stored files. Attachment is via document_links. DATA_MODEL.md 3.9."""
    __tablename__ = "documents"
    __table_args__ = (
        *tenant_indexes("documents"),
        Index("uq_documents_storage", "bucket", "storage_key", unique=True),
        Index("ix_documents_type_status", "client_id", "document_type", "status", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_documents_expiry", "client_id", "expires_at", postgresql_where=text("expires_at IS NOT NULL AND deleted_at IS NULL")),
        Index("ix_documents_checksum", "client_id", "checksum_sha256"),
        Index("ix_documents_ocr", "ocr_tsv", postgresql_using="gin"),
        CheckConstraint("supersedes_document_id <> id", name="ck_documents_no_self_supersede"),
        CheckConstraint("byte_size >= 0", name="ck_documents_size_nonneg"),
        {"comment": "Stored files. Attachment is via document_links. DATA_MODEL.md 3.9."},
    )

    document_type: DocumentType = Field(sa_column=Column("document_type", pg_enum(DocumentType), nullable=False))
    status: DocumentStatus = Field(default=DocumentStatus.PENDING, sa_column=Column("status", pg_enum(DocumentStatus), nullable=False, server_default="pending"))
    title: str = Field(sa_column=Column("title", Text, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column("description", Text))
    storage_provider: StorageProvider = Field(default=StorageProvider.S3, sa_column=Column("storage_provider", pg_enum(StorageProvider), nullable=False, server_default="s3"))
    bucket: str = Field(sa_column=Column("bucket", Text, nullable=False))
    storage_key: str = Field(sa_column=Column("storage_key", Text, nullable=False))
    filename: str = Field(sa_column=Column("filename", Text, nullable=False))
    mime_type: str = Field(sa_column=Column("mime_type", Text, nullable=False))
    byte_size: int = Field(sa_column=Column("byte_size", BigInteger, nullable=False))
    checksum_sha256: str = Field(sa_column=Column("checksum_sha256", Text, nullable=False))
    version: int = Field(default=1, sa_column=Column("version", SmallInteger, nullable=False, server_default="1"))
    supersedes_document_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("supersedes_document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL")))
    is_confidential: bool = Field(default=False, sa_column=Column("is_confidential", Boolean, nullable=False, server_default=text("false")))
    effective_date: Optional[date] = Field(default=None, sa_column=Column("effective_date", Date))
    expires_at: Optional[date] = Field(default=None, sa_column=Column("expires_at", Date))
    retention_until: Optional[date] = Field(default=None, sa_column=Column("retention_until", Date))
    uploaded_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("uploaded_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    ocr_text: Optional[str] = Field(default=None, sa_column=Column("ocr_text", Text))
    ocr_tsv: Optional[Any] = Field(default=None, sa_column=Column("ocr_tsv", TSVECTOR, Computed("to_tsvector('english'::regconfig, coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(ocr_text, ''))", persisted=True)))
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")))

    links: list["DocumentLink"] = Relationship(back_populates="document", cascade_delete=True)


class DocumentLink(BitluxBase, TenantScopedMixin, table=True):
    """Polymorphic attachment of documents to entities. DATA_MODEL.md 3.9."""
    __tablename__ = "document_links"
    __table_args__ = (
        *tenant_indexes("document_links"),
        Index("uq_document_links", "document_id", "entity_type", "entity_id", "link_role", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_document_links_entity", "client_id", "entity_type", "entity_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_document_links_document", "client_id", "document_id"),
        {"comment": "Polymorphic attachment of documents to entities. DATA_MODEL.md 3.9."},
    )

    document_id: uuid.UUID = Field(sa_column=Column("document_id", UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False))
    entity_type: EntityType = Field(sa_column=Column("entity_type", pg_enum(EntityType), nullable=False))
    entity_id: uuid.UUID = Field(sa_column=Column("entity_id", UUID(as_uuid=True), nullable=False))
    link_role: str = Field(default="attachment", sa_column=Column("link_role", Text, nullable=False, server_default="attachment"))
    is_primary: bool = Field(default=False, sa_column=Column("is_primary", Boolean, nullable=False, server_default=text("false")))

    document: Optional["Document"] = Relationship(back_populates="links")


class Task(BitluxBase, TenantScopedMixin, table=True):
    """Work queue, human and automated. DATA_MODEL.md 3.9."""
    __tablename__ = "tasks"
    __table_args__ = (
        *tenant_indexes("tasks"),
        Index("uq_tasks_dedupe", "client_id", "dedupe_key", unique=True, postgresql_where=text("dedupe_key IS NOT NULL AND status IN ('open','in_progress')")),
        Index("ix_tasks_assignee", "client_id", "assigned_to_user_id", "status", "due_at", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_tasks_entity", "client_id", "entity_type", "entity_id", postgresql_where=text("deleted_at IS NULL")),
        Index("ix_tasks_open_due", "client_id", "due_at", postgresql_where=text("status IN ('open','in_progress')")),
        Index("ix_tasks_priority", "client_id", "priority", "due_at", postgresql_where=text("status = 'open'")),
        CheckConstraint("(entity_type IS NULL) = (entity_id IS NULL)", name="ck_tasks_entity_pair"),
        CheckConstraint("status <> 'completed' OR completed_at IS NOT NULL", name="ck_tasks_completed_at"),
        CheckConstraint("parent_task_id <> id", name="ck_tasks_no_self_parent"),
        {"comment": "Work queue, human and automated. DATA_MODEL.md 3.9."},
    )

    title: str = Field(sa_column=Column("title", Text, nullable=False))
    description: Optional[str] = Field(default=None, sa_column=Column("description", Text))
    task_type: TaskType = Field(default=TaskType.OTHER, sa_column=Column("task_type", pg_enum(TaskType), nullable=False, server_default="other"))
    status: TaskStatus = Field(default=TaskStatus.OPEN, sa_column=Column("status", pg_enum(TaskStatus), nullable=False, server_default="open"))
    priority: TaskPriority = Field(default=TaskPriority.NORMAL, sa_column=Column("priority", pg_enum(TaskPriority), nullable=False, server_default="normal"))
    assigned_to_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("assigned_to_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    assigned_team: Optional[str] = Field(default=None, sa_column=Column("assigned_team", Text))
    entity_type: Optional[EntityType] = Field(default=None, sa_column=Column("entity_type", pg_enum(EntityType)))
    entity_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("entity_id", UUID(as_uuid=True)))
    parent_task_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("parent_task_id", UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE")))
    due_at: Optional[datetime] = Field(default=None, sa_column=Column("due_at", TIMESTAMP(timezone=True)))
    reminder_at: Optional[datetime] = Field(default=None, sa_column=Column("reminder_at", TIMESTAMP(timezone=True)))
    started_at: Optional[datetime] = Field(default=None, sa_column=Column("started_at", TIMESTAMP(timezone=True)))
    completed_at: Optional[datetime] = Field(default=None, sa_column=Column("completed_at", TIMESTAMP(timezone=True)))
    completed_by_user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("completed_by_user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    blocked_reason: Optional[str] = Field(default=None, sa_column=Column("blocked_reason", Text))
    recurrence_rule: Optional[str] = Field(default=None, sa_column=Column("recurrence_rule", Text))
    sla_due_at: Optional[datetime] = Field(default=None, sa_column=Column("sla_due_at", TIMESTAMP(timezone=True)))
    sla_breached_at: Optional[datetime] = Field(default=None, sa_column=Column("sla_breached_at", TIMESTAMP(timezone=True)))
    source_system: Optional[str] = Field(default=None, sa_column=Column("source_system", Text))
    dedupe_key: Optional[str] = Field(default=None, sa_column=Column("dedupe_key", Text))


class Activity(BitluxBase, TenantScopedMixin, table=True):
    """CRM interaction log. DATA_MODEL.md 3.9."""
    __tablename__ = "activities"
    __table_args__ = (
        *tenant_indexes("activities"),
        Index("ix_activities_contact", "client_id", "contact_id", text("occurred_at DESC"), postgresql_where=text("deleted_at IS NULL")),
        Index("ix_activities_entity", "client_id", "entity_type", "entity_id", text("occurred_at DESC"), postgresql_where=text("deleted_at IS NULL")),
        Index("ix_activities_user", "client_id", "user_id", text("occurred_at DESC")),
        Index("ix_activities_occurred", "client_id", text("occurred_at DESC")),
        CheckConstraint("(entity_type IS NULL) = (entity_id IS NULL)", name="ck_activities_entity_pair"),
        {"comment": "CRM interaction log. DATA_MODEL.md 3.9."},
    )

    activity_type: ActivityType = Field(sa_column=Column("activity_type", pg_enum(ActivityType), nullable=False))
    direction: ActivityDirection = Field(default=ActivityDirection.OUTBOUND, sa_column=Column("direction", pg_enum(ActivityDirection), nullable=False, server_default="outbound"))
    subject: Optional[str] = Field(default=None, sa_column=Column("subject", Text))
    body: Optional[str] = Field(default=None, sa_column=Column("body", Text))
    user_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("user_id", UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")))
    contact_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("contact_id", UUID(as_uuid=True), ForeignKey("contacts.id", ondelete="CASCADE")))
    account_holder_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("account_holder_id", UUID(as_uuid=True), ForeignKey("account_holders.id", ondelete="CASCADE")))
    entity_type: Optional[EntityType] = Field(default=None, sa_column=Column("entity_type", pg_enum(EntityType)))
    entity_id: Optional[uuid.UUID] = Field(default=None, sa_column=Column("entity_id", UUID(as_uuid=True)))
    occurred_at: datetime = Field(default_factory=utcnow, sa_column=Column("occurred_at", TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")))
    duration_minutes: Optional[int] = Field(default=None, sa_column=Column("duration_minutes", Integer))
    external_ref: Optional[str] = Field(default=None, sa_column=Column("external_ref", Text))
    metadata_: dict[str, Any] = Field(default_factory=dict, sa_column=Column("metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")))

    contact: Optional["Contact"] = Relationship(back_populates="activities")


class Tag(BitluxBase, TenantScopedMixin, table=True):
    """Free-form labels. DATA_MODEL.md 3.9."""
    __tablename__ = "tags"
    __table_args__ = (
        *tenant_indexes("tags"),
        Index("uq_tags_name", "client_id", "name", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_tags_category", "client_id", "category"),
        {"comment": "Free-form labels. DATA_MODEL.md 3.9."},
    )

    name: str = Field(sa_column=Column("name", CITEXT, nullable=False))
    category: Optional[str] = Field(default=None, sa_column=Column("category", Text))
    color: Optional[str] = Field(default=None, sa_column=Column("color", Text))
    description: Optional[str] = Field(default=None, sa_column=Column("description", Text))

    entity_tags: list["EntityTag"] = Relationship(back_populates="tag", cascade_delete=True)


class EntityTag(BitluxBase, TenantScopedMixin, table=True):
    """Polymorphic tagging. DATA_MODEL.md 3.9."""
    __tablename__ = "entity_tags"
    __table_args__ = (
        *tenant_indexes("entity_tags"),
        Index("uq_entity_tags", "tag_id", "entity_type", "entity_id", unique=True, postgresql_where=text("deleted_at IS NULL")),
        Index("ix_entity_tags_entity", "client_id", "entity_type", "entity_id"),
        Index("ix_entity_tags_tag", "client_id", "tag_id"),
        {"comment": "Polymorphic tagging. DATA_MODEL.md 3.9."},
    )

    tag_id: uuid.UUID = Field(sa_column=Column("tag_id", UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False))
    entity_type: EntityType = Field(sa_column=Column("entity_type", pg_enum(EntityType), nullable=False))
    entity_id: uuid.UUID = Field(sa_column=Column("entity_id", UUID(as_uuid=True), nullable=False))

    tag: Optional["Tag"] = Relationship(back_populates="entity_tags")
