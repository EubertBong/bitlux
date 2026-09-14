"""Alembic environment for the Bitlux CRM backend.

Configured for:

* ``DATABASE_URL`` read from the environment (optionally via ``backend/.env``),
  so the same config drives local Docker, CI, and Neon with no file edits.
* An **async** engine (asyncpg), matching the runtime driver.
* SQLModel metadata imported for *future* autogenerate support.

A note on autogenerate
----------------------
``target_metadata`` points at ``SQLModel.metadata``. Until the ORM models in
``app/models.py`` actually describe every table, autogenerate would see an empty
metadata and happily emit ``DROP TABLE`` for the entire schema. ``env.py``
therefore refuses to autogenerate while the metadata is empty -- see
``_guard_autogenerate``. Migrations 001-015 are hand-written on purpose: most of
this schema (partial indexes, generated columns, EXCLUDE constraints, RLS,
partitioning) is not expressible via autogenerate anyway.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# Make ``app`` importable when alembic runs from the backend/ directory.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

# Load backend/.env if python-dotenv is installed. Real environment variables
# always win over the file.
try:
    from dotenv import load_dotenv

    load_dotenv(pathlib.Path(__file__).resolve().parents[1] / ".env", override=False)
except ImportError:  # pragma: no cover - dotenv is a convenience, not a requirement
    pass

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def _database_url() -> str:
    """Resolve the database URL and normalise it to the asyncpg driver."""
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Export it, or create backend/.env from "
            "backend/.env.example. For local Docker:\n"
            "  DATABASE_URL=postgresql+asyncpg://bitlux:bitlux@localhost:5433/bitlux_crm"
        )
    # Accept the plain libpq form that Neon and psql hand out, and the psycopg
    # form, and steer both onto asyncpg.
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if url.startswith("postgresql+psycopg2://"):
        url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
    # asyncpg does not accept libpq's ?sslmode= query parameter.
    if "sslmode=" in url:
        from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

        parts = urlsplit(url)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k != "sslmode"]
        url = urlunsplit(parts._replace(query=urlencode(query)))
    return url


config.set_main_option("sqlalchemy.url", _database_url())

# --- Metadata for future autogenerate ---------------------------------------
# Importing app.models registers every SQLModel table on SQLModel.metadata.
from sqlmodel import SQLModel  # noqa: E402

import app.models  # noqa: F401,E402  (imported for its registration side effects)

target_metadata = SQLModel.metadata


def _guard_autogenerate() -> None:
    """Refuse to autogenerate against empty metadata.

    Without this, ``alembic revision --autogenerate`` on a schema whose ORM
    models do not exist yet emits a migration that drops every table.
    """
    if context.config.cmd_opts is None:
        return
    if getattr(context.config.cmd_opts, "autogenerate", False) and not target_metadata.tables:
        raise RuntimeError(
            "Refusing to autogenerate: SQLModel.metadata is empty, so the diff "
            "would be 'drop everything'. Define the ORM models in app/models.py "
            "first, or write the migration by hand (see alembic/versions/)."
        )


def _include_object(obj, name, type_, reflected, compare_to) -> bool:
    """Keep autogenerate away from objects it cannot model correctly."""
    # audit_logs partitions are created by migration 012, not by the ORM.
    if type_ == "table" and name and name.startswith("audit_logs_"):
        return False
    return True


def run_migrations_offline() -> None:
    """Emit SQL to stdout without connecting (``alembic upgrade --sql``)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        include_object=_include_object,
        # Keep enum/extension DDL and table DDL in one transaction per migration
        # so a failure leaves nothing half-applied.
        transaction_per_migration=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against a live async connection."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(_do_run_migrations)
    await connectable.dispose()


_guard_autogenerate()

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
