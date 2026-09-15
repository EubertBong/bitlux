"""Shared connection plumbing for the operational scripts in this directory.

Every script here talks to the database through this module so that DATABASE_URL
handling, the asyncpg codecs the schema needs, and the "act as the application
role" dance live in exactly one place.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import uuid
from dataclasses import dataclass

import asyncpg

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]

# The role the application connects as; see DATA_MODEL.md 1.7.
APP_ROLE = "bitlux_app"


def load_env() -> None:
    """Load backend/.env if python-dotenv is available. Real env always wins."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        return
    load_dotenv(BACKEND_DIR / ".env", override=False)


def dsn() -> str:
    """DATABASE_URL normalised to something asyncpg.connect() accepts.

    The app and alembic use the SQLAlchemy form ``postgresql+asyncpg://``;
    asyncpg itself wants plain ``postgresql://``.
    """
    load_env()
    url = os.getenv("DATABASE_URL")
    if not url:
        sys.exit(
            "DATABASE_URL is not set. For the local stack:\n"
            "  export DATABASE_URL=postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm"
        )
    for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://", "postgresql+psycopg://"):
        if url.startswith(prefix):
            url = "postgresql://" + url[len(prefix):]
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


async def connect() -> asyncpg.Connection:
    """Connect and register the codecs this schema needs.

    * ``citext`` has no binary codec in asyncpg; it is text on the wire.
    * ``jsonb`` round-trips as Python dicts/lists.
    """
    conn = await asyncpg.connect(dsn())
    await conn.set_builtin_type_codec("citext", codec_name="text")
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog"
    )
    return conn


@dataclass(frozen=True)
class RoleInfo:
    current_user: str
    is_superuser: bool
    bypass_rls: bool

    @property
    def rls_enforced(self) -> bool:
        return not (self.is_superuser or self.bypass_rls)


async def role_info(conn: asyncpg.Connection) -> RoleInfo:
    row = await conn.fetchrow(
        """
        SELECT current_user::text AS current_user,
               current_setting('is_superuser') = 'on' AS is_superuser,
               (SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user) AS bypass_rls
        """
    )
    return RoleInfo(row["current_user"], row["is_superuser"], row["bypass_rls"])


async def enter_tenant(conn: asyncpg.Connection, client_id: uuid.UUID, *, role: str = APP_ROLE) -> RoleInfo:
    """Inside an open transaction: become the app role and select the tenant.

    Mirrors exactly what the application does per request (DATA_MODEL.md 1.7):
    ``SET LOCAL ROLE`` so privilege and RLS checks run as the non-superuser
    role, then ``app.client_id`` via ``set_config(..., is_local => true)`` so it
    cannot leak past this transaction. Refuses to continue if the resulting
    session would still bypass RLS -- a seed or a check that ran with RLS off
    would prove nothing.
    """
    info = await role_info(conn)
    if info.current_user != role:
        try:
            await conn.execute(f"SET LOCAL ROLE {role}")
        except asyncpg.InsufficientPrivilegeError:
            # A superuser may SET ROLE to anything, so this never happens on the
            # local stack. A non-superuser owner (Neon) must be a *member* first.
            print(
                f"\nCannot SET ROLE {role}: the connecting user {info.current_user!r} must be a member of it.\n"
                f"Run 'make app-role-prod' (it grants membership), or as the owner:\n"
                f"    GRANT {role} TO CURRENT_USER;\n",
                file=sys.stderr,
            )
            raise
        info = await role_info(conn)
    if not info.rls_enforced:
        raise RuntimeError(
            f"Row-Level Security is NOT enforced for role {info.current_user!r} "
            f"(superuser={info.is_superuser}, bypassrls={info.bypass_rls}). "
            "Refusing to proceed: everything below would run with tenant isolation off."
        )
    await conn.fetchval("SELECT set_config('app.client_id', $1, true)", str(client_id))
    return info
