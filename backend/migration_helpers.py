"""Shared DDL helpers for the Bitlux CRM migrations.

Importable from migration scripts because ``alembic.ini`` sets
``prepend_sys_path = .`` (and ``env.py`` adds ``backend/`` to ``sys.path``).

Deliberately NOT placed under ``alembic/`` -- a module named ``alembic.helpers``
would shadow the installed ``alembic`` package.

Everything here encodes the conventions in DATA_MODEL.md section 1.1 / 1.2 so
that 37 tables do not repeat the same seven columns and three indexes by hand.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as pg

__all__ = [
    "APP_ROLE",
    "grant_app_dml",
    "UUID",
    "LTREE",
    "TS",
    "CITEXT",
    "JSONB",
    "pgenum",
    "id_col",
    "audit_cols",
    "std_cols",
    "std_indexes",
    "drop_std_indexes",
    "tsv",
    "money",
    "SHARED_CATALOG_TABLES",
    "add_fk",
]

UUID = pg.UUID(as_uuid=True)
JSONB = pg.JSONB
CITEXT = pg.CITEXT

# The role the application connects as (DATA_MODEL 1.7). Bootstrapped NOLOGIN in
# migration 001 if it does not already exist; local dev creates it LOGIN earlier
# via docker/initdb. Privileges are granted table-by-table in the migration that
# creates each table, so a table has no DML for the app until a migration says so
# -- "append-only" (SELECT, INSERT) is the ceiling until then.
APP_ROLE = "bitlux_app"


def grant_app_dml(*tables: str) -> None:
    """Grant full DML on ordinary tenant tables to the application role.

    Deliberately NOT called for audit_logs (migration 012), which gets
    SELECT, INSERT only. Every UPDATE/DELETE grant in the schema is therefore
    an explicit, greppable line in a migration.
    """
    for table in tables:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP_ROLE}")


class LTREE(sa.types.UserDefinedType):
    """The ``ltree`` type from the extension installed in migration 001.

    SQLAlchemy has no built-in ltree type, and a plain ``Text`` column would
    silently lose the GiST operator class that makes ancestry queries fast.
    """

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "ltree"


def TS() -> sa.TIMESTAMP:
    """``timestamptz`` -- the only instant type used (DATA_MODEL 1.2)."""
    return sa.TIMESTAMP(timezone=True)


def pgenum(name: str) -> pg.ENUM:
    """Reference an enum created in migration 002.

    ``create_type=False`` stops SQLAlchemy from trying to emit ``CREATE TYPE``
    again for every column that uses it.
    """
    return pg.ENUM(name=name, create_type=False)


def money() -> sa.BigInteger:
    """Money is always ``bigint`` minor units, never float (DATA_MODEL 1.2)."""
    return sa.BigInteger()


def tsv(*columns: str, config: str = "english") -> str:
    """Build an IMMUTABLE ``to_tsvector`` expression for a generated column.

    The two-argument ``to_tsvector(regconfig, text)`` is immutable; the
    one-argument form is not, and cannot be used in a generated column.
    """
    parts = " || ' ' || ".join(f"coalesce({c}::text, '')" for c in columns)
    return f"to_tsvector('{config}'::regconfig, {parts})"


def id_col() -> sa.Column:
    """Primary key: UUIDv7 supplied by the application, no DB default.

    See DATA_MODEL.md 1.5 -- PG16 has no native ``uuidv7()`` and the app needs
    the id before the INSERT.
    """
    return sa.Column("id", UUID, primary_key=True, nullable=False)


def audit_cols(with_user_fks: bool = True) -> list[sa.Column]:
    """created_at / updated_at / deleted_at / created_by / updated_by.

    ``with_user_fks=False`` creates ``created_by``/``updated_by`` as plain
    columns, for tables built before ``users`` exists (migration 003). The FK
    constraints are added afterwards in migration 004.
    """
    return [
        sa.Column("created_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", TS(), nullable=False, server_default=sa.text("now()")),
        sa.Column("deleted_at", TS(), nullable=True),
        sa.Column(
            "created_by",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL") if with_user_fks else None,
            nullable=True,
        )
        if with_user_fks
        else sa.Column("created_by", UUID, nullable=True),
        sa.Column(
            "updated_by",
            UUID,
            sa.ForeignKey("users.id", ondelete="SET NULL") if with_user_fks else None,
            nullable=True,
        )
        if with_user_fks
        else sa.Column("updated_by", UUID, nullable=True),
    ]


def std_cols(
    *,
    client_nullable: bool = False,
    with_client_fk: bool = True,
    with_user_fks: bool = True,
) -> list[sa.Column]:
    """The full standard column block from DATA_MODEL.md 1.1.

    ``client_nullable=True``  -- shared reference catalog (DATA_MODEL 1.3):
                                 NULL means "global row, visible to every tenant".
    ``with_client_fk=False``  -- ``clients`` does not exist yet (migration 003);
                                 the FK is added in migration 004.
    """
    client = (
        sa.Column(
            "client_id",
            UUID,
            sa.ForeignKey("clients.id", ondelete="RESTRICT"),
            nullable=client_nullable,
        )
        if with_client_fk
        else sa.Column("client_id", UUID, nullable=client_nullable)
    )
    return [id_col(), client, *audit_cols(with_user_fks=with_user_fks)]


def std_indexes(table: str, *, live_probe: bool = True) -> None:
    """The three standard indexes from DATA_MODEL.md 1.1."""
    op.create_index(f"ix_{table}_client", table, ["client_id"])
    op.create_index(
        f"ix_{table}_client_created",
        table,
        ["client_id", sa.text("created_at DESC")],
    )
    if live_probe:
        op.create_index(
            f"ix_{table}_client_live",
            table,
            ["client_id", "id"],
            postgresql_where=sa.text("deleted_at IS NULL"),
        )


def drop_std_indexes(table: str, *, live_probe: bool = True) -> None:
    if live_probe:
        op.drop_index(f"ix_{table}_client_live", table_name=table)
    op.drop_index(f"ix_{table}_client_created", table_name=table)
    op.drop_index(f"ix_{table}_client", table_name=table)


def add_fk(
    name: str,
    source: str,
    referent: str,
    local: list[str],
    remote: list[str],
    *,
    ondelete: str | None = None,
    deferrable: bool = False,
) -> None:
    """Add a foreign key that could not be declared at CREATE TABLE time.

    Several FKs point forward to tables created in a later migration (the order
    of migrations 003-015 is fixed by the build plan). Those columns are created
    bare and the constraint is attached here, in the migration that creates the
    *referenced* table, so the dependency is always satisfiable and always
    reversible.
    """
    op.create_foreign_key(
        name,
        source,
        referent,
        local,
        remote,
        ondelete=ondelete,
        deferrable=deferrable or None,
        initially="DEFERRED" if deferrable else None,
    )


# Tables whose ``client_id`` is nullable because rows may be global
# (DATA_MODEL 1.3). Used by the RLS migration to pick the right policy shape and
# by the polymorphic validator to allow NULL-tenant rows.
SHARED_CATALOG_TABLES: tuple[str, ...] = (
    "manufacturers",
    "aircraft_models",
    "airports",
    "fbos",
)
