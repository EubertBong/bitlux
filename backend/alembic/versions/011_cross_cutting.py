"""011 - Cross-cutting: documents, tasks, activities, tags

DATA_MODEL.md 3.9.

Polymorphism (DATA_MODEL 5): ``document_links``, ``entity_tags``, ``tasks`` and
``activities`` all carry the same ``(entity_type, entity_id)`` key shape, so
"everything about this trip" is four indexed lookups of identical form.
PostgreSQL cannot FK a polymorphic column; integrity is enforced by the
validation trigger added in migration 013, backed by a nightly orphan sweep.

``documents`` holds the file; attachment is a separate link table so one file can
be attached to several entities (a charter agreement belongs to the booking, the
trip and the account holder) without being stored three times.

This migration also attaches every deferred FK that points at ``documents``:
seven columns created bare across migrations 005-010.

Revision ID: 011
Revises: 010
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from migration_helpers import CITEXT, JSONB, TS, UUID, pgenum, std_cols, std_indexes

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (constraint name, table, column) -- all point at documents.id.
DEFERRED_DOCUMENT_FKS: list[tuple[str, str, str]] = [
    ("fk_travel_documents_scan", "travel_documents", "scan_document_id"),
    ("fk_safety_ratings_report", "operator_safety_ratings", "report_document_id"),
    ("fk_aoa_mgmt_agreement", "aircraft_operator_assignments", "management_agreement_document_id"),
    ("fk_crew_members_photo", "crew_members", "photo_document_id"),
    ("fk_quotes_pdf", "quotes", "pdf_document_id"),
    ("fk_bookings_contract", "bookings", "contract_document_id"),
    ("fk_invoices_pdf", "invoices", "pdf_document_id"),
]


def upgrade() -> None:
    # ------------------------------------------------------------------- documents
    op.create_table(
        "documents",
        *std_cols(),
        sa.Column("document_type", pgenum("document_type"), nullable=False),
        sa.Column(
            "status", pgenum("document_status"), nullable=False, server_default="pending"
        ),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "storage_provider", pgenum("storage_provider"), nullable=False, server_default="s3"
        ),
        sa.Column("bucket", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.Text(), nullable=False),
        sa.Column("version", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column(
            "supersedes_document_id",
            UUID,
            sa.ForeignKey("documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_confidential", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("expires_at", sa.Date(), nullable=True),  # insurance, AOC, passport
        sa.Column("retention_until", sa.Date(), nullable=True),  # legal hold / purge floor
        sa.Column(
            "uploaded_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column(
            "ocr_tsv",
            pg.TSVECTOR(),
            sa.Computed(
                "to_tsvector('english'::regconfig, "
                "coalesce(title, '') || ' ' || coalesce(description, '') || ' ' "
                "|| coalesce(ocr_text, ''))",
                persisted=True,
            ),
            nullable=True,
        ),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "supersedes_document_id <> id", name="ck_documents_no_self_supersede"
        ),
        sa.CheckConstraint("byte_size >= 0", name="ck_documents_size_nonneg"),
        comment="Stored files. Attachment is via document_links. DATA_MODEL.md 3.9.",
    )
    std_indexes("documents")
    # One object in the bucket is one row.
    op.create_index(
        "uq_documents_storage", "documents", ["bucket", "storage_key"], unique=True
    )
    op.create_index(
        "ix_documents_type_status",
        "documents",
        ["client_id", "document_type", "status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Expiry sweep -> tasks (DATA_MODEL 5).
    op.create_index(
        "ix_documents_expiry",
        "documents",
        ["client_id", "expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index("ix_documents_checksum", "documents", ["client_id", "checksum_sha256"])
    op.create_index("ix_documents_ocr", "documents", ["ocr_tsv"], postgresql_using="gin")

    # -------------------------------------------------------------- document_links
    op.create_table(
        "document_links",
        *std_cols(),
        sa.Column(
            "document_id", UUID, sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("entity_type", pgenum("entity_type"), nullable=False),
        # POLYMORPHIC: no FK possible. Validated by trigger (migration 013).
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column(
            "link_role", sa.Text(), nullable=False, server_default="attachment"
        ),  # 'contract', 'passport_scan', ...
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        comment="Polymorphic attachment of documents to entities. DATA_MODEL.md 3.9.",
    )
    std_indexes("document_links")
    op.create_index(
        "uq_document_links",
        "document_links",
        ["document_id", "entity_type", "entity_id", "link_role"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # "every document attached to this trip"
    op.create_index(
        "ix_document_links_entity",
        "document_links",
        ["client_id", "entity_type", "entity_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_document_links_document", "document_links", ["client_id", "document_id"])

    # ----------------------------------------------------------------------- tasks
    op.create_table(
        "tasks",
        *std_cols(),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", pgenum("task_type"), nullable=False, server_default="other"),
        sa.Column("status", pgenum("task_status"), nullable=False, server_default="open"),
        sa.Column("priority", pgenum("task_priority"), nullable=False, server_default="normal"),
        sa.Column(
            "assigned_to_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("assigned_team", sa.Text(), nullable=True),
        # POLYMORPHIC subject, both NULL or both set.
        sa.Column("entity_type", pgenum("entity_type"), nullable=True),
        sa.Column("entity_id", UUID, nullable=True),
        sa.Column(
            "parent_task_id", UUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column("due_at", TS(), nullable=True),
        sa.Column("reminder_at", TS(), nullable=True),
        sa.Column("started_at", TS(), nullable=True),
        sa.Column("completed_at", TS(), nullable=True),
        sa.Column(
            "completed_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("blocked_reason", sa.Text(), nullable=True),
        sa.Column("recurrence_rule", sa.Text(), nullable=True),  # RFC 5545 RRULE
        sa.Column("sla_due_at", TS(), nullable=True),
        sa.Column("sla_breached_at", TS(), nullable=True),
        sa.Column("source_system", sa.Text(), nullable=True),  # 'manual','expiry_sweep'
        # Stops the nightly compliance sweep re-creating the same task every run.
        sa.Column("dedupe_key", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "(entity_type IS NULL) = (entity_id IS NULL)", name="ck_tasks_entity_pair"
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR completed_at IS NOT NULL", name="ck_tasks_completed_at"
        ),
        sa.CheckConstraint("parent_task_id <> id", name="ck_tasks_no_self_parent"),
        comment="Work queue, human and automated. DATA_MODEL.md 3.9.",
    )
    std_indexes("tasks")
    op.create_index(
        "uq_tasks_dedupe",
        "tasks",
        ["client_id", "dedupe_key"],
        unique=True,
        postgresql_where=sa.text(
            "dedupe_key IS NOT NULL AND status IN ('open','in_progress')"
        ),
    )
    op.create_index(
        "ix_tasks_assignee",
        "tasks",
        ["client_id", "assigned_to_user_id", "status", "due_at"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_tasks_entity",
        "tasks",
        ["client_id", "entity_type", "entity_id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # "my queue" -- the hottest read in the app.
    op.create_index(
        "ix_tasks_open_due",
        "tasks",
        ["client_id", "due_at"],
        postgresql_where=sa.text("status IN ('open','in_progress')"),
    )
    op.create_index(
        "ix_tasks_priority",
        "tasks",
        ["client_id", "priority", "due_at"],
        postgresql_where=sa.text("status = 'open'"),
    )

    # ------------------------------------------------------------------ activities
    # Human-facing interaction log. Deliberately separate from audit_logs, which
    # is machine-written and immutable (DATA_MODEL 5, "Audit vs activities").
    op.create_table(
        "activities",
        *std_cols(),
        sa.Column("activity_type", pgenum("activity_type"), nullable=False),
        sa.Column(
            "direction",
            pgenum("activity_direction"),
            nullable=False,
            server_default="outbound",
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        sa.Column(
            "contact_id", UUID, sa.ForeignKey("contacts.id", ondelete="CASCADE"), nullable=True
        ),
        sa.Column(
            "account_holder_id",
            UUID,
            sa.ForeignKey("account_holders.id", ondelete="CASCADE"),
            nullable=True,
        ),
        # POLYMORPHIC, in addition to the two typed FKs above.
        sa.Column("entity_type", pgenum("entity_type"), nullable=True),
        sa.Column("entity_id", UUID, nullable=True),
        sa.Column("occurred_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("external_ref", sa.Text(), nullable=True),  # email Message-ID
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint(
            "(entity_type IS NULL) = (entity_id IS NULL)", name="ck_activities_entity_pair"
        ),
        comment="CRM interaction log. DATA_MODEL.md 3.9.",
    )
    std_indexes("activities")
    op.create_index(
        "ix_activities_contact",
        "activities",
        ["client_id", "contact_id", sa.text("occurred_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_activities_entity",
        "activities",
        ["client_id", "entity_type", "entity_id", sa.text("occurred_at DESC")],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_activities_user", "activities", ["client_id", "user_id", sa.text("occurred_at DESC")]
    )
    op.create_index(
        "ix_activities_occurred", "activities", ["client_id", sa.text("occurred_at DESC")]
    )

    # ------------------------------------------------------------------------ tags
    op.create_table(
        "tags",
        *std_cols(),
        sa.Column("name", CITEXT(), nullable=False),
        sa.Column("category", sa.Text(), nullable=True),  # 'risk','preference','campaign'
        sa.Column("color", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        comment="Free-form labels. DATA_MODEL.md 3.9.",
    )
    std_indexes("tags")
    op.create_index(
        "uq_tags_name",
        "tags",
        ["client_id", "name"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_tags_category", "tags", ["client_id", "category"])

    # ---------------------------------------------------------------- entity_tags
    op.create_table(
        "entity_tags",
        *std_cols(),
        sa.Column("tag_id", UUID, sa.ForeignKey("tags.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", pgenum("entity_type"), nullable=False),
        # POLYMORPHIC: validated by trigger (migration 013).
        sa.Column("entity_id", UUID, nullable=False),
        comment="Polymorphic tagging. DATA_MODEL.md 3.9.",
    )
    std_indexes("entity_tags")
    op.create_index(
        "uq_entity_tags",
        "entity_tags",
        ["tag_id", "entity_type", "entity_id"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_entity_tags_entity", "entity_tags", ["client_id", "entity_type", "entity_id"]
    )
    op.create_index("ix_entity_tags_tag", "entity_tags", ["client_id", "tag_id"])

    # ------------------- deferred FKs from migrations 005, 006, 007, 010 ----------
    # SET NULL rather than CASCADE: deleting a stored file must never delete the
    # passport record, safety rating or invoice that referenced it.
    for name, table, column in DEFERRED_DOCUMENT_FKS:
        op.create_foreign_key(
            name, table, "documents", [column], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    for name, table, _column in reversed(DEFERRED_DOCUMENT_FKS):
        op.drop_constraint(name, table, type_="foreignkey")
    op.drop_table("entity_tags")
    op.drop_table("tags")
    op.drop_table("activities")
    op.drop_table("tasks")
    op.drop_table("document_links")
    op.drop_table("documents")
