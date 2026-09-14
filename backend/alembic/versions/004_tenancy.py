"""004 - Tenancy: clients and users

DATA_MODEL.md 3.1.

``clients`` is the tenant root: it is the ONLY table without a ``client_id``,
and the only one whose RLS policy keys on ``id`` rather than ``client_id``.

This migration also attaches the foreign keys that migration 003 could not
declare, because ``clients`` and ``users`` did not exist yet. Those columns were
created bare; the constraints land here so the reference catalog is fully wired
before any tenant data exists.

Revision ID: 004
Revises: 003
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from migration_helpers import (
    CITEXT,
    JSONB,
    TS,
    audit_cols,
    id_col,
    pgenum,
    std_cols,
    std_indexes,
)

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Tables created in 003, before clients/users existed.
CATALOG_TABLES = ("manufacturers", "aircraft_models", "airports", "fbos")


def upgrade() -> None:
    # --------------------------------------------------------------------- clients
    # No client_id (this IS the tenant), and no created_by/updated_by -- a client
    # row predates every user that could have authored it.
    op.create_table(
        "clients",
        id_col(),
        sa.Column("slug", CITEXT(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("legal_name", sa.Text(), nullable=True),
        sa.Column(
            "status", pgenum("client_status"), nullable=False, server_default="trialing"
        ),
        sa.Column("default_currency", sa.CHAR(3), nullable=False, server_default="USD"),
        sa.Column("timezone", sa.Text(), nullable=False, server_default="UTC"),  # IANA
        sa.Column("locale", sa.Text(), nullable=False, server_default="en-US"),
        sa.Column("billing_email", CITEXT(), nullable=True),
        sa.Column("support_email", CITEXT(), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("settings", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "feature_flags", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("trip_number_prefix", sa.Text(), nullable=True),  # e.g. 'BLX'
        sa.Column("created_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", TS(), nullable=True),
        comment="Tenant root. DATA_MODEL.md 3.1.",
    )
    op.create_index(
        "uq_clients_slug",
        "clients",
        ["slug"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_clients_status",
        "clients",
        ["status"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # ----------------------------------------------------------------------- users
    # created_by/updated_by are self-referential here, which is fine in one CREATE.
    op.create_table(
        "users",
        *std_cols(),
        sa.Column("email", CITEXT(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("given_name", sa.Text(), nullable=True),
        sa.Column("family_name", sa.Text(), nullable=True),
        sa.Column("role", pgenum("user_role"), nullable=False, server_default="broker"),
        sa.Column("status", pgenum("user_status"), nullable=False, server_default="invited"),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("timezone", sa.Text(), nullable=True),
        # Authentication is delegated to an external IdP; no password hash here.
        sa.Column("auth_provider", sa.Text(), nullable=True),   # 'oidc','saml','password'
        sa.Column("auth_subject", sa.Text(), nullable=True),    # external subject claim
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_login_at", TS(), nullable=True),
        comment="Staff users of a tenant. DATA_MODEL.md 3.1.",
    )
    std_indexes("users")
    op.create_index(
        "uq_users_client_email",
        "users",
        ["client_id", "email"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    # Global, not tenant-scoped: one IdP subject maps to exactly one row.
    op.create_index(
        "uq_users_auth_subject",
        "users",
        ["auth_provider", "auth_subject"],
        unique=True,
        postgresql_where=sa.text("auth_subject IS NOT NULL"),
    )
    op.create_index(
        "ix_users_client_role",
        "users",
        ["client_id", "role"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_users_client_status", "users", ["client_id", "status"])

    # --------------------------------------------- deferred FKs from migration 003
    # The reference catalog was created before clients/users existed. Wire it up now.
    for table in CATALOG_TABLES:
        op.create_foreign_key(
            f"fk_{table}_client", table, "clients", ["client_id"], ["id"], ondelete="RESTRICT"
        )
        op.create_foreign_key(
            f"fk_{table}_created_by", table, "users", ["created_by"], ["id"], ondelete="SET NULL"
        )
        op.create_foreign_key(
            f"fk_{table}_updated_by", table, "users", ["updated_by"], ["id"], ondelete="SET NULL"
        )


def downgrade() -> None:
    for table in CATALOG_TABLES:
        op.drop_constraint(f"fk_{table}_updated_by", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_created_by", table, type_="foreignkey")
        op.drop_constraint(f"fk_{table}_client", table, type_="foreignkey")
    op.drop_table("users")
    op.drop_table("clients")
