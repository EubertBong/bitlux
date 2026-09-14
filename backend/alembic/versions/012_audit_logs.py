"""012 - audit_logs, monthly RANGE partitions

DATA_MODEL.md 3.9 and 5 ("Audit vs activities").

Append-only and machine-written. It answers "who changed this field", which is
why it has no ``deleted_at``, no ``updated_at`` and no ``updated_by`` -- an audit
row that can be edited is not an audit row. UPDATE/DELETE are blocked two ways:

  * grants  -- the application role is granted SELECT, INSERT only, and
               UPDATE/DELETE are revoked from it and from PUBLIC, here, before
               the first partition exists. Migration 015 asserts this at the
               end of the chain so a later grant cannot silently undo it.
  * trigger -- migration 013 adds an immutability trigger that fires even for
               the table owner, so the guarantee also holds in local dev where
               the app connects as owner.

Partitioning
------------
RANGE on ``occurred_at``, one partition per month, because this table is the
fastest-growing in the schema and retention is by age: a partition older than
24 months is detached and moved to cold storage in one DDL statement instead of
a multi-hour DELETE.

The primary key is ``(id, occurred_at)``: PostgreSQL requires the partition key
to be part of every unique constraint on a partitioned table.

A DEFAULT partition catches rows outside every defined range so an insert can
never fail. The tradeoff: while rows exist in the default partition, ATTACHing a
new monthly partition must scan it to prove no row belongs there. Keep the
default empty -- provision new months ahead of time (see ``_month_starts``) and
alert if it is ever non-empty.

Revision ID: 012
Revises: 011
Create Date: 2026-09-14

"""
from __future__ import annotations

from datetime import date
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from migration_helpers import APP_ROLE, JSONB, TS, UUID, pgenum

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# First month provisioned. Fixed rather than computed from "today" so that
# running this migration later still produces an identical schema.
FIRST_MONTH = date(2026, 9, 1)
MONTHS_AHEAD = 12


def _month_starts(start: date, count: int) -> list[tuple[date, date]]:
    """Return ``count`` [month_start, next_month_start) pairs."""
    out: list[tuple[date, date]] = []
    year, month = start.year, start.month
    for _ in range(count):
        lo = date(year, month, 1)
        year2, month2 = (year + 1, 1) if month == 12 else (year, month + 1)
        out.append((lo, date(year2, month2, 1)))
        year, month = year2, month2
    return out


PARTITIONS = _month_starts(FIRST_MONTH, MONTHS_AHEAD)


def upgrade() -> None:
    op.create_table(
        "audit_logs",
        # Composite PK: partition key must participate.
        sa.Column("id", UUID, primary_key=True, nullable=False),
        sa.Column(
            "occurred_at",
            TS(),
            primary_key=True,
            nullable=False,
            server_default=sa.text("now()"),
        ),
        # NULLABLE: platform-level events (a failed login against no known
        # tenant) have no client. RESTRICT so a tenant with history cannot be
        # hard-deleted out from under its own audit trail.
        sa.Column(
            "client_id", UUID, sa.ForeignKey("clients.id", ondelete="RESTRICT"), nullable=True
        ),
        # Written when the row was persisted, which can lag occurred_at when
        # events are buffered.
        sa.Column("created_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("action", pgenum("audit_action"), nullable=False),
        sa.Column("entity_type", pgenum("entity_type"), nullable=False),
        sa.Column("entity_id", UUID, nullable=True),
        # Denormalized label so the trail stays readable after the row it
        # describes is gone.
        sa.Column("entity_label", sa.Text(), nullable=True),
        sa.Column("actor_type", pgenum("actor_type"), nullable=False, server_default="user"),
        sa.Column(
            "actor_user_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True
        ),
        # Name + email as they were at event time; survives the user's deletion.
        sa.Column("actor_label", sa.Text(), nullable=False),
        sa.Column(
            "impersonated_by_user_id",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("api_key_id", UUID, nullable=True),
        sa.Column("changed_fields", pg.ARRAY(sa.Text()), nullable=True),
        # MUST be redacted for [enc] fields before insert -- an audit trail that
        # logs plaintext passport numbers defeats the encryption entirely
        # (DATA_MODEL 5, "Encryption boundary").
        sa.Column("before", JSONB(), nullable=True),
        sa.Column("after", JSONB(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("request_id", UUID, nullable=True),
        sa.Column("session_id", sa.Text(), nullable=True),
        sa.Column("ip_address", pg.INET(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        postgresql_partition_by="RANGE (occurred_at)",
        comment="Append-only audit trail, monthly partitions. DATA_MODEL.md 3.9.",
    )

    # --- Append-only privileges, set before any partition exists -----------------
    # The application role gets SELECT + INSERT and nothing else. The REVOKEs are
    # belt-and-braces (nothing has granted UPDATE/DELETE here), but they make the
    # intent explicit and undo any ALTER DEFAULT PRIVILEGES a deployment may have.
    # Migration 015 asserts this still holds at the end of the chain.
    op.execute(f"GRANT SELECT, INSERT ON audit_logs TO {APP_ROLE}")
    op.execute(f"REVOKE UPDATE, DELETE ON audit_logs FROM {APP_ROLE}")
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")

    # --- Monthly partitions + a default catch-all --------------------------------
    for lo, hi in PARTITIONS:
        name = f"audit_logs_{lo:%Y_%m}"
        op.execute(
            f"CREATE TABLE {name} PARTITION OF audit_logs "
            f"FOR VALUES FROM ('{lo:%Y-%m-%d}') TO ('{hi:%Y-%m-%d}')"
        )
    op.execute("CREATE TABLE audit_logs_default PARTITION OF audit_logs DEFAULT")

    # Partitions are reachable only through the parent. PostgreSQL checks
    # privileges on the table named in the query, so the parent's SELECT/INSERT
    # grant is sufficient for every partition -- and a partition has no RLS
    # policy of its own, so any *direct* grant on one would be a cross-tenant
    # read. Revoke anything a deployment's ALTER DEFAULT PRIVILEGES may have
    # handed out. scripts/partition_maintenance.py does the same for partitions
    # it creates later.
    for lo, _hi in PARTITIONS:
        op.execute(f"REVOKE ALL ON audit_logs_{lo:%Y_%m} FROM {APP_ROLE}")
    op.execute(f"REVOKE ALL ON audit_logs_default FROM {APP_ROLE}")

    # --- Indexes (created on the parent, propagated to every partition) ----------
    # "the history of this record"
    op.create_index(
        "ix_audit_logs_entity",
        "audit_logs",
        ["client_id", "entity_type", "entity_id", sa.text("occurred_at DESC")],
    )
    # "what did this user do"
    op.create_index(
        "ix_audit_logs_actor",
        "audit_logs",
        ["client_id", "actor_user_id", sa.text("occurred_at DESC")],
    )
    op.create_index(
        "ix_audit_logs_action",
        "audit_logs",
        ["client_id", "action", sa.text("occurred_at DESC")],
    )
    # BRIN: rows arrive in occurred_at order, so a tiny summary index answers
    # time-range scans that a btree would need gigabytes for.
    op.execute("CREATE INDEX ix_audit_logs_occurred_brin ON audit_logs USING BRIN (occurred_at)")
    # Value forensics: "which row ever held this value".
    op.execute(
        "CREATE INDEX ix_audit_logs_after_gin ON audit_logs USING GIN (after jsonb_path_ops)"
    )

    op.execute(
        "COMMENT ON TABLE audit_logs IS "
        "'Append-only. The application role holds SELECT, INSERT only (migration 012, "
        "asserted in 015); UPDATE/DELETE are additionally blocked for every role, "
        "owner included, by trigger trg_audit_logs_immutable (migration 013).'"
    )


def downgrade() -> None:
    # Dropping the parent drops every partition with it.
    op.drop_table("audit_logs")
