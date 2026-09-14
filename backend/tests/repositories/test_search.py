"""/search's engine: search_ids() (migration 017) -- tenant-scoped, and able to use
the GIN indexes where a plain `@@` under RLS cannot."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.repositories import SearchRepository, tenant_transaction

OWNER_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm")


async def test_search_ids_is_tenant_scoped_and_fails_closed(session, demo_id, seed_id):
    rows = await session.execute(text(
        "SELECT id FROM search_ids('contacts', websearch_to_tsquery('english', 'halcyon') || to_tsquery('english', 'halcyon:*'), 5)"))
    assert {r.id for r in rows} == {seed_id("contact:halcyon"), seed_id("contact:daniel")}

    # another tenant sees nothing, even though the function runs with row_security off
    async with tenant_transaction(session, uuid.uuid5(demo_id, "search-other"), None):
        n = (await session.execute(text("SELECT count(*) FROM search_ids('contacts', websearch_to_tsquery('english','halcyon'), 5)"))).scalar_one()
        assert n == 0
    # and an unset tenant is not "all tenants"
    await session.execute(text("SELECT set_config('app.client_id', '', true)"))
    n = (await session.execute(text("SELECT count(*) FROM search_ids('contacts', websearch_to_tsquery('english','halcyon'), 5)"))).scalar_one()
    assert n == 0
    await session.execute(text("SELECT set_config('app.client_id', :c, true)"), {"c": str(demo_id)})

    with pytest.raises(Exception, match="unknown type"):
        async with session.begin_nested():
            await session.execute(text("SELECT * FROM search_ids('users', websearch_to_tsquery('english','x'), 5)"))


async def test_search_repository_grouped_results(session):
    repo = SearchRepository(session)
    out = await repo.search("halcyon")
    assert [h.label for h in out["contacts"]] == ["Halcyon Capital Partners", "Daniel Okafor"] or \
           {h.label for h in out["contacts"]} == {"Halcyon Capital Partners", "Daniel Okafor"}
    assert out["contacts"][0].url.startswith("/contacts/") and out["contacts"][0].rank > 0
    assert "manufacturers" in await repo.search("gulf"), "prefix term: 'gulf' finds Gulfstream"
    assert [h.label for h in (await repo.search("BLX-2026-001", ["trips"]))["trips"]] == ["BLX-2026-001"]
    assert await repo.search("   ") == {}


async def test_search_ids_inner_query_uses_gin_index_at_volume():
    """The function body runs as the owner with row_security off. Run that same
    statement the same way against a tenant with 50k contacts (loaded and
    ANALYZEd inside a rolled-back transaction, as the owner -- a non-owner's
    ANALYZE is silently skipped) and the *default* planner must choose the GIN
    index. At seed size a btree on client_id is cheaper, so small-table plans
    prove nothing either way; this is the claim at the size where it matters."""
    engine = create_async_engine(OWNER_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        trans = await conn.begin()
        try:
            await conn.execute(text(
                "INSERT INTO contacts (id, client_id, contact_type, display_name, first_name, last_name) "
                "SELECT gen_random_uuid(), :c, 'individual', 'Synthetic Person ' || g, 'Synthetic', 'Person' || g "
                "FROM generate_series(1, 50000) g"), {"c": "867278a8-ba28-51cd-8240-1f48423fe086"})
            await conn.execute(text("SELECT gin_clean_pending_list('ix_contacts_search')"))
            await conn.execute(text("ANALYZE contacts"))
            plan = "\n".join(r[0] for r in await conn.execute(text(
                "EXPLAIN SELECT t.id, ts_rank(t.search_tsv, q) FROM contacts t, websearch_to_tsquery('english','halcyon') q "
                "WHERE t.deleted_at IS NULL AND t.client_id = '867278a8-ba28-51cd-8240-1f48423fe086' AND t.search_tsv @@ q "
                "ORDER BY 2 DESC LIMIT 5")))
            assert "Bitmap Index Scan on ix_contacts_search" in plan, plan
            # ...and the direct form under RLS, as the app role, cannot get there (the reason 017 exists)
            await conn.execute(text("SET LOCAL ROLE bitlux_app"))
            await conn.execute(text("SELECT set_config('app.client_id', '867278a8-ba28-51cd-8240-1f48423fe086', true)"))
            rls_plan = "\n".join(r[0] for r in await conn.execute(text(
                "EXPLAIN SELECT id FROM contacts WHERE deleted_at IS NULL AND client_id = '867278a8-ba28-51cd-8240-1f48423fe086' "
                "AND search_tsv @@ websearch_to_tsquery('english','halcyon') LIMIT 5")))
            assert "ix_contacts_search" not in rls_plan and "Seq Scan" in rls_plan, rls_plan
        finally:
            await trans.rollback()
    await engine.dispose()
