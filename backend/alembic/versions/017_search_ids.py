"""017 - search_ids(): full-text search that can use the GIN indexes under RLS

Additive only.

The problem
-----------
Row-Level Security policy quals are security barriers. PostgreSQL will not
evaluate a non-LEAKPROOF operator as an *index condition* underneath one, and
``@@`` (``ts_match_vq``) is not leakproof -- nor are ``ILIKE`` / ``~~``. So for
``bitlux_app`` every ``search_tsv @@ query`` becomes a filter applied after the
tenant qual, never an index scan: with 50k contacts in a tenant, a seq scan at
~15 ms per type, against 0.04 ms for the Bitmap Index Scan the owner gets for
the identical statement. Marking the catalog function LEAKPROOF fixes it but
needs superuser, which Neon does not give us, and mutates pg_catalog.

The fix
-------
``search_ids(p_type, p_query, p_limit)`` is a SECURITY DEFINER function owned by
the schema owner that runs with ``row_security = off`` -- so inside it the GIN
index is usable -- and enforces tenant scoping itself with the same trust root
the RLS policies use, ``current_client_id()``. It contains no dynamic SQL: one
static branch per whitelisted type, each with ``deleted_at IS NULL`` and the
tenant predicate, returning only ``(id, rank)``. The application joins those ids
from a query that is itself still under RLS, so the final rows pass the policy
a second time. This is the second and last deliberate SECURITY DEFINER read,
next to ``auth_lookup_user()`` (016); both are documented in DATA_MODEL.md 1.7.

Revision ID: 017
Revises: 016
Create Date: 2026-09-14

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

from migration_helpers import APP_ROLE

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _branch(table: str, tsv: str, catalog: bool = False) -> str:
    tenant = "(t.client_id IS NULL OR t.client_id = v_tenant)" if catalog else "t.client_id = v_tenant"
    return (
        f"RETURN QUERY SELECT t.id, ts_rank({tsv}, p_query) FROM {table} t "
        f"WHERE t.deleted_at IS NULL AND {tenant} AND {tsv} @@ p_query "
        f"ORDER BY 2 DESC, t.id LIMIT p_limit;"
    )


# Mirrors app/repositories/search.py::SEARCH_TYPES. Keep in step.
BRANCHES = {
    "contacts": _branch("contacts", "t.search_tsv"),
    "passengers": _branch("passengers", "t.search_tsv"),
    "operators": _branch("operators", "t.search_tsv"),
    "aircraft": _branch("aircraft", "t.search_tsv"),
    "documents": _branch("documents", "t.ocr_tsv"),
    "airports": _branch("airports", "t.search_tsv", catalog=True),
    "manufacturers": _branch("manufacturers", "t.search_tsv", catalog=True),
    "aircraft_models": _branch("aircraft_models", "t.search_tsv", catalog=True),
    "trips": _branch("trips", "to_tsvector('simple', t.trip_number::text)"),
    "quotes": _branch("quotes", "to_tsvector('simple', t.quote_number::text)"),
}


def upgrade() -> None:
    arms = "\n".join(f"        WHEN '{name}' THEN {sql}" for name, sql in BRANCHES.items())
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION search_ids(p_type text, p_query tsquery, p_limit integer DEFAULT 5)
        RETURNS TABLE (id uuid, rank real)
        LANGUAGE plpgsql STABLE SECURITY DEFINER
        SET search_path = public
        SET row_security = off
        AS $$
        DECLARE
            v_tenant uuid := current_client_id();   -- NULL when unset: every branch returns nothing
        BEGIN
            IF p_limit IS NULL OR p_limit < 1 THEN p_limit := 5; END IF;
            IF p_limit > 100 THEN p_limit := 100; END IF;
            CASE p_type
        {arms}
                ELSE RAISE EXCEPTION 'search_ids: unknown type %', p_type USING ERRCODE = 'invalid_parameter_value';
            END CASE;
        END $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION search_ids(text, tsquery, integer) FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION search_ids(text, tsquery, integer) TO {APP_ROLE}")
    op.execute(
        "COMMENT ON FUNCTION search_ids(text, tsquery, integer) IS "
        "'Full-text search ids for one type. SECURITY DEFINER with row_security off so the GIN "
        "indexes are usable (@@ is not leakproof, so RLS blocks them as index conditions). "
        "Tenant-scoped by current_client_id(); static SQL only; returns ids and ranks. See 017.'"
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS search_ids(text, tsquery, integer)")
