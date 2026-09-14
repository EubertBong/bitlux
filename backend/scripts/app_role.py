"""Ensure the runtime role exists with LOGIN and a password -- the production
counterpart of docker/initdb/10-app-role.sql.

Locally the docker-entrypoint creates bitlux_app. On Neon nobody does: migration
001 creates it NOLOGIN if missing (so the GRANTs have a target), but the API needs
to *connect* as it. Idempotent; re-run to rotate the password.

    DATABASE_URL=<owner url> APP_DB_PASSWORD=<new password> python scripts/app_role.py

Why a separate role at all: Neon's console-created roles are members of
neon_superuser, which carries BYPASSRLS, and BYPASSRLS ignores even FORCE ROW
LEVEL SECURITY. The API refuses to start as such a role. See DATA_MODEL.md 1.7.
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import quote, urlsplit

from _db import APP_ROLE, connect, dsn, role_info


async def main() -> int:
    password = os.getenv("APP_DB_PASSWORD")
    if not password or len(password) < 16:
        sys.exit("APP_DB_PASSWORD must be set (>= 16 chars). Generate one:  python -c 'import secrets; print(secrets.token_urlsafe(24))'")
    conn = await connect()
    try:
        who = await role_info(conn)
        db = await conn.fetchval("SELECT current_database()")
        print(f"connected as {who.current_user} to {db}")
        exists = await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", APP_ROLE)
        async with conn.transaction():
            # Role names cannot be bound parameters; APP_ROLE is a constant, the password is quoted.
            pw = password.replace("'", "''")
            if exists:
                await conn.execute(f"ALTER ROLE {APP_ROLE} WITH LOGIN PASSWORD '{pw}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT")
                print(f"{APP_ROLE}: exists -> LOGIN enabled, password set")
            else:
                await conn.execute(f"CREATE ROLE {APP_ROLE} WITH LOGIN PASSWORD '{pw}' NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT")
                print(f"{APP_ROLE}: created")
            await conn.execute(f'GRANT CONNECT ON DATABASE "{db}" TO {APP_ROLE}')
            await conn.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
            # Same safety-net defaults as the local initdb script: read + append only for
            # anything the owner creates outside the migration chain.
            await conn.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {who.current_user} IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO {APP_ROLE}")
            await conn.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {who.current_user} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}")
        row = await conn.fetchrow("SELECT rolcanlogin, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = $1", APP_ROLE)
        assert row["rolcanlogin"] and not row["rolbypassrls"] and not row["rolsuper"], dict(row)
        parts = urlsplit(dsn())
        host = f"{parts.hostname}{':' + str(parts.port) if parts.port else ''}"
        print("\nAPP_DATABASE_URL for the API (Render):")
        print(f"  postgresql+asyncpg://{APP_ROLE}:{quote(password, safe='')}@{host}{parts.path}?sslmode=require")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
