"""Ensure the runtime role exists with LOGIN, a password, its grants, and --
crucially -- membership for the connecting owner. The production counterpart of
docker/initdb/10-app-role.sql.

Locally the docker-entrypoint creates bitlux_app. On Neon nobody does: migration
001 creates it NOLOGIN if missing (so the GRANTs have a target), but the API needs
to *connect* as it. Idempotent; re-run to rotate the password.

    DATABASE_URL=<owner url> APP_DB_PASSWORD=<new password> python scripts/app_role.py

Why a separate role at all: Neon's console-created roles are members of
neon_superuser, which carries BYPASSRLS, and BYPASSRLS ignores even FORCE ROW
LEVEL SECURITY. The API refuses to start as such a role. See DATA_MODEL.md 1.7.

Why the membership grant: the seed and the verify script write tenant data via
``SET LOCAL ROLE bitlux_app`` so RLS is exercised. A real superuser may SET ROLE
to anything, which is why this works locally without ceremony; the Neon owner is
not a superuser, and PostgreSQL only lets a role SET ROLE to roles it is a member
of. Without ``GRANT bitlux_app TO <owner>`` the seed fails with
"permission denied to set role".
"""

from __future__ import annotations

import asyncio
import os
import sys
from urllib.parse import quote, urlsplit

import asyncpg

from _db import APP_ROLE, connect, dsn, role_info

MEMBERSHIP_SQL = """
SELECT EXISTS (
    SELECT 1 FROM pg_auth_members m
    JOIN pg_roles r ON r.oid = m.roleid
    JOIN pg_roles u ON u.oid = m.member
    WHERE r.rolname = $1 AND u.rolname = $2
)
"""


async def ensure_app_role(conn: asyncpg.Connection, password: str) -> dict:
    """Create or update the app role; grant CONNECT / USAGE / defaults; grant
    membership to the connecting user. Returns a dict describing the result.

    Per-table DML is deliberately NOT granted here: each migration grants it via
    grant_app_dml(), and audit_logs must never receive UPDATE/DELETE (015).
    """
    who = await role_info(conn)
    db = await conn.fetchval("SELECT current_database()")
    existed = bool(await conn.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", APP_ROLE))
    pw = password.replace("'", "''")  # role names cannot be bound parameters; APP_ROLE is a constant
    attrs = "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS INHERIT"
    async with conn.transaction():
        if existed:
            await conn.execute(f"ALTER ROLE {APP_ROLE} WITH {attrs} PASSWORD '{pw}'")
        else:
            await conn.execute(f"CREATE ROLE {APP_ROLE} WITH {attrs} PASSWORD '{pw}'")
        await conn.execute(f'GRANT CONNECT ON DATABASE "{db}" TO {APP_ROLE}')
        await conn.execute(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}")
        # Same safety-net defaults as the local initdb script: read + append only for
        # anything the owner creates outside the migration chain.
        await conn.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {who.current_user} IN SCHEMA public GRANT SELECT, INSERT ON TABLES TO {APP_ROLE}")
        await conn.execute(f"ALTER DEFAULT PRIVILEGES FOR ROLE {who.current_user} IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE}")
        # Membership: lets the owner SET ROLE bitlux_app for RLS-scoped writes (seed,
        # verify). CURRENT_USER, not a name, so it is right locally and on Neon.
        await conn.execute(f"GRANT {APP_ROLE} TO CURRENT_USER")
    row = await conn.fetchrow("SELECT rolcanlogin, rolbypassrls, rolsuper FROM pg_roles WHERE rolname = $1", APP_ROLE)
    member = await conn.fetchval(MEMBERSHIP_SQL, APP_ROLE, who.current_user)
    return {"role": APP_ROLE, "created": not existed, "owner": who.current_user, "database": db,
            "login": row["rolcanlogin"], "bypassrls": row["rolbypassrls"], "superuser": row["rolsuper"],
            "owner_is_member": bool(member)}


def app_database_url(owner_dsn: str, password: str) -> str:
    parts = urlsplit(owner_dsn)
    host = f"{parts.hostname}{':' + str(parts.port) if parts.port else ''}"
    return f"postgresql+asyncpg://{APP_ROLE}:{quote(password, safe='')}@{host}{parts.path}?sslmode=require"


async def main() -> int:
    password = os.getenv("APP_DB_PASSWORD")
    if not password or len(password) < 16:
        sys.exit("APP_DB_PASSWORD must be set (>= 16 chars). Generate one:  python -c 'import secrets; print(secrets.token_urlsafe(24))'")
    conn = await connect()
    try:
        result = await ensure_app_role(conn, password)
        print(f"connected as {result['owner']} to {result['database']}")
        print(f"{APP_ROLE}: {'created' if result['created'] else 'exists -> LOGIN enabled, password set'}")
        print(f"{APP_ROLE}: login={result['login']} bypassrls={result['bypassrls']} superuser={result['superuser']}")
        print(f"{result['owner']} is a member of {APP_ROLE}: {result['owner_is_member']}  (needed for SET LOCAL ROLE in seed/verify)")
        if result["bypassrls"] or result["superuser"] or not result["login"] or not result["owner_is_member"]:
            print("ERROR: role state is not what the API needs", file=sys.stderr)
            return 1
        print("\nAPP_DATABASE_URL for the API (Render):")
        print(f"  {app_database_url(dsn(), password)}")
        return 0
    finally:
        await conn.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
