"""014 - Row-Level Security policies

DATA_MODEL.md 1.7.

Enables RLS with a tenant-isolation policy on every table. Read 1.7 before
trusting this to protect anything -- the short version:

* **A table's owner is exempt from its own RLS policies.** Locally the app
  connects as ``bitlux``, which owns everything, so policies would be inert.
  This migration therefore also applies ``FORCE ROW LEVEL SECURITY``, which
  makes them apply to the owner too, so isolation is exercised in dev and CI
  rather than discovered in production.
* **Production must connect as a non-owner role** and ``SET LOCAL app.client_id``
  per transaction. ``SET LOCAL`` (not ``SET``) is required under transaction
  pooling, or the tenant leaks across pooled connections.

``current_client_id()`` reads the session variable with ``missing_ok`` and maps
'' to NULL, so an unset tenant yields NULL, every predicate evaluates to NULL,
and **no rows are visible** -- failing closed.

Three policy shapes:

  tenant  -- client_id = current_client_id()
  catalog -- client_id IS NULL OR client_id = current_client_id()  (read global
             rows, but WITH CHECK still forces writes to be tenant-owned)
  clients -- id = current_client_id()  (the tenant root keys on its own id)

Revision ID: 014
Revises: 013
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Shared reference catalog: global rows (client_id IS NULL) are readable by all.
CATALOG_TABLES: tuple[str, ...] = ("manufacturers", "aircraft_models", "airports", "fbos")

# Ordinary tenant tables: client_id NOT NULL, strict equality.
TENANT_TABLES: tuple[str, ...] = (
    "users",
    "segments", "contacts", "contact_channels", "addresses", "passengers",
    "account_holders", "account_holder_passengers", "travel_documents",
    "operators", "operator_safety_ratings", "aircraft",
    "aircraft_operator_assignments",
    "crew_members",
    "trips", "legs", "leg_passengers", "leg_crew",
    "empty_legs",
    "quotes", "quote_line_items", "bookings", "invoices", "invoice_line_items",
    "payments",
    "documents", "document_links", "tasks", "activities", "tags", "entity_tags",
)

# audit_logs is handled separately: client_id is nullable (platform events), and
# the policy deliberately hides those from tenants rather than exposing NULLs.
ALL_RLS_TABLES = ("clients",) + CATALOG_TABLES + TENANT_TABLES + ("audit_logs",)


def upgrade() -> None:
    # --------------------------------------------------------- tenant accessor
    op.execute(
        """
        CREATE OR REPLACE FUNCTION current_client_id() RETURNS uuid
        LANGUAGE sql STABLE AS $$
            SELECT NULLIF(current_setting('app.client_id', true), '')::uuid
        $$;
        """
    )
    op.execute(
        "COMMENT ON FUNCTION current_client_id() IS "
        "'Current tenant from the app.client_id session variable. Returns NULL when "
        "unset so every RLS predicate fails closed. Set it with SET LOCAL inside a "
        "transaction -- see DATA_MODEL.md 1.7.'"
    )

    # ------------------------------------------------------------ clients (root)
    op.execute("ALTER TABLE clients ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE clients FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY clients_tenant_isolation ON clients
        USING (id = current_client_id())
        WITH CHECK (id = current_client_id());
        """
    )

    # --------------------------------------------------- shared reference catalog
    for table in CATALOG_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        # Readable: global rows plus this tenant's own overrides.
        # Writable: only this tenant's own rows -- a tenant must never be able to
        # edit or create a global catalog entry.
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (client_id IS NULL OR client_id = current_client_id())
            WITH CHECK (client_id = current_client_id());
            """
        )

    # ------------------------------------------------------------ tenant tables
    for table in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_tenant_isolation ON {table}
            USING (client_id = current_client_id())
            WITH CHECK (client_id = current_client_id());
            """
        )

    # ---------------------------------------------------------------- audit_logs
    # Enabling RLS on the partitioned parent covers every partition.
    # Platform-level rows (client_id IS NULL) stay invisible to tenants.
    op.execute("ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY audit_logs_tenant_isolation ON audit_logs
        USING (client_id = current_client_id())
        WITH CHECK (client_id = current_client_id());
        """
    )


def downgrade() -> None:
    for table in reversed(ALL_RLS_TABLES):
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
    op.execute("DROP FUNCTION IF EXISTS current_client_id()")
