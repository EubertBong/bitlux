"""scripts/app_role.py: the production role bootstrap.

Runs as the schema OWNER (DATABASE_URL; backend/.env supplies it locally, CI sets
it). The password passed is the one already in APP_DATABASE_URL, so re-setting it
is a no-op and the rest of the suite keeps connecting as bitlux_app.
"""

from __future__ import annotations

import os
import pathlib
import sys
from urllib.parse import unquote, urlsplit

import asyncpg
import pytest

SCRIPTS = pathlib.Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from _db import APP_ROLE, dsn, load_env  # noqa: E402
from app_role import MEMBERSHIP_SQL, app_database_url, ensure_app_role  # noqa: E402

load_env()
pytestmark = pytest.mark.skipif(not os.getenv("DATABASE_URL"), reason="needs the owner DATABASE_URL")


def _current_app_password() -> str:
    url = os.getenv("APP_DATABASE_URL", "postgresql+asyncpg://bitlux_app:bitlux_app@localhost:5433/bitlux_crm")
    return unquote(urlsplit(url).password or "bitlux_app")


@pytest.fixture
async def owner():
    conn = await asyncpg.connect(dsn())
    try:
        yield conn
    finally:
        await conn.close()


async def test_app_role_grants_membership(owner):
    """After the bootstrap, the connecting owner is an explicit member of bitlux_app.

    pg_has_role() would be vacuously true for a superuser, so check pg_auth_members:
    the explicit GRANT is what a non-superuser owner (Neon) needs to SET ROLE.
    """
    result = await ensure_app_role(owner, _current_app_password())
    assert result["role"] == APP_ROLE
    assert result["login"] and not result["bypassrls"] and not result["superuser"]
    assert result["owner_is_member"] is True
    assert await owner.fetchval(MEMBERSHIP_SQL, APP_ROLE, result["owner"]) is True
    # And the thing membership is for: the seed's SET LOCAL ROLE inside a transaction.
    async with owner.transaction():
        await owner.execute(f"SET LOCAL ROLE {APP_ROLE}")
        assert await owner.fetchval("SELECT current_user") == APP_ROLE


async def test_app_role_is_idempotent(owner):
    first = await ensure_app_role(owner, _current_app_password())
    second = await ensure_app_role(owner, _current_app_password())
    assert first["created"] is False or second["created"] is False
    assert second["created"] is False
    assert second["owner_is_member"] is True
    # Membership is recorded once, not duplicated by re-runs.
    n = await owner.fetchval(
        "SELECT count(*) FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.roleid "
        "JOIN pg_roles u ON u.oid = m.member WHERE r.rolname = $1 AND u.rolname = current_user", APP_ROLE)
    assert n == 1


def test_app_database_url_uses_asyncpg_scheme():
    url = app_database_url("postgresql://owner:pw@ep-x.neon.tech/bitlux_crm?sslmode=require", "p@ss/word")
    assert url == "postgresql+asyncpg://bitlux_app:p%40ss%2Fword@ep-x.neon.tech/bitlux_crm?sslmode=require"
