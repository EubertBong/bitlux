"""Login must COMMIT: the refresh token and audit row have to be visible from a
different connection afterwards.

The regular API fixtures share one session inside a rolled-back transaction, so
a handler that forgets to commit still looks correct there. This test gives the
app real per-request sessions (as production does), logs in, then checks the
database from an independent connection, and cleans up as the owner.
"""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.deps import get_session
from app.main import create_app
from app.security.tokens import fingerprint

from ..conftest import APP_DATABASE_URL, DEMO
from .conftest import API, DEMO_PASSWORD

OWNER_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm")


@pytest.fixture
async def real_sessions():
    engine = create_async_engine(APP_DATABASE_URL, poolclass=NullPool)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield maker
    finally:
        await engine.dispose()


async def _owner_cleanup(sql: str, params: dict) -> None:
    owner = create_async_engine(OWNER_DATABASE_URL, poolclass=NullPool)
    async with AsyncSession(owner) as s:
        await s.execute(text(sql), params)
        await s.commit()
    await owner.dispose()


async def test_login_commits_refresh_token_and_audit_row(real_sessions):
    app = create_app()

    async def _real_session():
        async with real_sessions() as s:  # a fresh session per request, like production
            yield s

    app.dependency_overrides[get_session] = _real_session
    hashes: list[str] = []
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(f"{API}/auth/login", json={"email": "ops@demo.test", "password": DEMO_PASSWORD})
            assert r.status_code == 200, r.text
            refresh_token = r.json()["refresh_token"]
            hashes.append(fingerprint(refresh_token))
            assert r.cookies.get("bitlux_refresh") == refresh_token, "the HttpOnly cookie must carry the same token the body does"

            # Visible from an independent connection => it was committed.
            async with real_sessions() as probe:
                await probe.execute(text("SELECT set_config('app.client_id', :c, true)"), {"c": str(DEMO)})
                n = (await probe.execute(text("SELECT count(*) FROM refresh_tokens WHERE token_hash = :h AND revoked_at IS NULL"), {"h": hashes[0]})).scalar_one()
                assert n == 1, "login did not commit its refresh token row"
                audit = (await probe.execute(text("SELECT count(*) FROM audit_logs WHERE action = 'login' AND occurred_at > now() - interval '1 minute'"))).scalar_one()
                assert audit >= 1, "login did not commit its audit row"
                await probe.rollback()

            # The cookie alone (no body) is enough to refresh, and refresh rotates.
            r2 = await client.post(f"{API}/auth/refresh")
            assert r2.status_code == 200, r2.text
            hashes.append(fingerprint(r2.json()["refresh_token"]))
            assert (await client.post(f"{API}/auth/refresh", json={"refresh_token": refresh_token})).status_code == 401, "old token must be dead after rotation"
    finally:
        await _owner_cleanup("DELETE FROM refresh_tokens WHERE token_hash = ANY(:hashes)", {"hashes": hashes})


async def test_tenant_transaction_commits_an_autobegun_transaction(real_sessions):
    """The exact shape of the login bug: a statement before tenant_transaction()
    autobegins; the block must still commit, not merely release a savepoint."""
    from app.repositories import TagRepository, tenant_transaction

    name = f"commit-probe-{uuid.uuid4().hex[:8]}"
    try:
        async with real_sessions() as s:
            await s.execute(text("SELECT 1"))  # autobegin, as login_candidates() does
            assert s.in_transaction()
            async with tenant_transaction(s, DEMO, None):
                await TagRepository(s).create({"name": name})
        async with real_sessions() as other:
            async with tenant_transaction(other, DEMO, None):
                assert await TagRepository(other).by_name(name) is not None, "row written inside the outermost tenant_transaction must be committed"
    finally:
        await _owner_cleanup("DELETE FROM tags WHERE name = :n", {"n": name})
