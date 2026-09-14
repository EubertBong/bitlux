"""Connectivity check for a database URL: SELECT 1, plus the facts you want to know
before pointing a deployment at it. Exit 0 and print OK, or exit 1.

    DATABASE_URL=postgresql://... python scripts/db_check.py
"""

from __future__ import annotations

import asyncio
import sys
from urllib.parse import urlsplit

from _db import connect, dsn, role_info


async def main() -> int:
    parts = urlsplit(dsn())
    target = f"{parts.hostname}:{parts.port or 5432}{parts.path}"
    try:
        conn = await connect()
    except Exception as exc:  # noqa: BLE001 -- report and exit non-zero, whatever it was
        print(f"FAIL  {target}: {type(exc).__name__}: {exc}")
        return 1
    try:
        one = await conn.fetchval("SELECT 1")
        if one != 1:
            print(f"FAIL  {target}: SELECT 1 returned {one!r}")
            return 1
        who = await role_info(conn)
        version = await conn.fetchval("SHOW server_version")
        head = await conn.fetchval("SELECT version_num FROM alembic_version") if await conn.fetchval(
            "SELECT to_regclass('public.alembic_version') IS NOT NULL") else None
        app_role = await conn.fetchrow("SELECT rolcanlogin, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = 'bitlux_app'")
        print(f"OK    {target}")
        print(f"      server      : PostgreSQL {version}")
        print(f"      connected as: {who.current_user} (superuser={who.is_superuser}, bypassrls={who.bypass_rls}) "
              f"-> RLS {'enforced' if who.rls_enforced else 'BYPASSED (owner/maintenance role)'}")
        print(f"      alembic     : {head or 'no alembic_version table (run make migrate-prod)'}")
        if app_role is None:
            print("      bitlux_app  : missing (run make app-role-prod)")
        else:
            print(f"      bitlux_app  : login={app_role['rolcanlogin']} bypassrls={app_role['rolbypassrls']} superuser={app_role['rolsuper']}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
