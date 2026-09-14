"""016 - Authentication support and full-text search indexes

Additive only; nothing shipped in 001-015 is modified.

Authentication (Sprint 3, API):
  * users.password_hash / password_changed_at -- argon2id hashes. The model had
    assumed an external IdP (auth_provider / auth_subject); first-party login
    needs a credential store. NULL means "cannot log in with a password".
  * refresh_tokens -- server-side state for refresh rotation and logout. Stores a
    SHA-256 of the token, never the token, so a database leak yields nothing
    presentable to /auth/refresh. Ordinary tenant table: RLS, grants, trigger.
  * auth_lookup_user() -- the one deliberate hole in tenant isolation. Login has
    to find a user by email *before* the tenant is known, which RLS forbids the
    app role. This SECURITY DEFINER function does exactly that lookup and
    nothing else, runs with row_security off as the schema owner, returns the
    minimum the login flow needs, and is the only thing bitlux_app may execute
    across tenants. Everything after login runs under RLS as usual.

Search (/search):
  * GIN indexes on to_tsvector('simple', trip_number / quote_number) so number
    search is an index scan like every other search type.
  * search_tsv generated columns + GIN on manufacturers and aircraft_models,
    which 003 did not give a tsvector (they were not expected to be searched).

Revision ID: 016
Revises: 015
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

from migration_helpers import APP_ROLE, TS, UUID, grant_app_dml, std_cols, std_indexes, tsv

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------ users: credentials
    op.add_column("users", sa.Column("password_hash", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("password_changed_at", TS(), nullable=True))

    # --------------------------------------------------------------- refresh_tokens
    op.create_table(
        "refresh_tokens",
        *std_cols(),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),  # sha256(token), never the token
        sa.Column("issued_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("expires_at", TS(), nullable=False),
        sa.Column("revoked_at", TS(), nullable=True),
        # Rotation chain: the token this one was exchanged for.
        sa.Column("replaced_by_id", UUID, sa.ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip_address", pg.INET(), nullable=True),
        sa.CheckConstraint("expires_at > issued_at", name="ck_refresh_tokens_expiry"),
        comment="Refresh-token state for rotation and logout. Stores a hash, never the token.",
    )
    std_indexes("refresh_tokens")
    op.create_index("uq_refresh_tokens_hash", "refresh_tokens", ["token_hash"], unique=True)
    op.create_index("ix_refresh_tokens_user", "refresh_tokens", ["client_id", "user_id"])
    op.create_index(
        "ix_refresh_tokens_active", "refresh_tokens", ["expires_at"],
        postgresql_where=sa.text("revoked_at IS NULL"),
    )
    grant_app_dml("refresh_tokens")
    op.execute(
        "CREATE TRIGGER set_updated_at_refresh_tokens BEFORE UPDATE ON refresh_tokens "
        "FOR EACH ROW EXECUTE FUNCTION trg_set_updated_at()"
    )
    op.execute("ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY refresh_tokens_tenant_isolation ON refresh_tokens "
        "USING (client_id = current_client_id()) WITH CHECK (client_id = current_client_id())"
    )

    # ----------------------------------------------------- cross-tenant login lookup
    op.execute(
        """
        CREATE OR REPLACE FUNCTION auth_lookup_user(p_email text, p_client_slug text DEFAULT NULL)
        RETURNS TABLE (
            user_id       uuid,
            client_id     uuid,
            client_slug   text,
            role          user_role,
            status        user_status,
            client_status client_status,
            password_hash text
        )
        LANGUAGE sql STABLE SECURITY DEFINER
        SET search_path = public
        SET row_security = off
        AS $$
            SELECT u.id, u.client_id, c.slug::text, u.role, u.status, c.status, u.password_hash
            FROM users u
            JOIN clients c ON c.id = u.client_id
            WHERE u.email = p_email::citext
              AND u.deleted_at IS NULL
              AND c.deleted_at IS NULL
              AND (p_client_slug IS NULL OR c.slug = p_client_slug::citext)
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION auth_lookup_user(text, text) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION auth_lookup_user(text, text) TO {APP_ROLE}")
    op.execute(
        "COMMENT ON FUNCTION auth_lookup_user(text, text) IS "
        "'Login-time lookup by email across tenants. SECURITY DEFINER with row_security off: "
        "the only cross-tenant read the application role can perform. Returns the minimum "
        "the login flow needs; everything after login runs under RLS.'"
    )

    # ------------------------------------------------------------- search indexes
    op.execute("CREATE INDEX ix_trips_number_search ON trips USING GIN (to_tsvector('simple', trip_number::text))")
    op.execute("CREATE INDEX ix_quotes_number_search ON quotes USING GIN (to_tsvector('simple', quote_number::text))")
    op.execute(
        f"ALTER TABLE manufacturers ADD COLUMN search_tsv tsvector "
        f"GENERATED ALWAYS AS ({tsv('name', 'short_name', 'code')}) STORED"
    )
    op.execute("CREATE INDEX ix_manufacturers_search ON manufacturers USING GIN (search_tsv)")
    op.execute(
        f"ALTER TABLE aircraft_models ADD COLUMN search_tsv tsvector "
        f"GENERATED ALWAYS AS ({tsv('name', 'family', 'icao_type_code')}) STORED"
    )
    op.execute("CREATE INDEX ix_aircraft_models_search ON aircraft_models USING GIN (search_tsv)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_aircraft_models_search")
    op.execute("ALTER TABLE aircraft_models DROP COLUMN IF EXISTS search_tsv")
    op.execute("DROP INDEX IF EXISTS ix_manufacturers_search")
    op.execute("ALTER TABLE manufacturers DROP COLUMN IF EXISTS search_tsv")
    op.execute("DROP INDEX IF EXISTS ix_quotes_number_search")
    op.execute("DROP INDEX IF EXISTS ix_trips_number_search")
    op.execute("DROP FUNCTION IF EXISTS auth_lookup_user(text, text)")
    op.drop_table("refresh_tokens")
    op.drop_column("users", "password_changed_at")
    op.drop_column("users", "password_hash")
