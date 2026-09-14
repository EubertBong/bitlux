"""Building blocks shared by every model: id/tenant/timestamp mixins, the enum binder,
the two extension types SQLAlchemy lacks, and the standard per-table indexes.

Conventions come from DATA_MODEL.md 1.1 / 1.2 / 1.5.

Why the mixins use ``sa_type`` + ``sa_column_kwargs`` and not ``sa_column``:
a ``Column`` object can belong to exactly one ``Table``. A ``Column`` created once
on a mixin would be attached to the first subclass and then rejected by the
second. ``sa_type``/``sa_column_kwargs`` describe a column and let SQLModel build
a fresh one per model. Table-specific fields in the modules do use ``sa_column``,
where there is only ever one owner.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import uuid_utils
from sqlalchemy import Index, text
from sqlalchemy.dialects.postgresql import ENUM, UUID
from sqlalchemy.types import TIMESTAMP, UserDefinedType
from sqlmodel import Field, SQLModel

__all__ = [
    "uuid7", "utcnow", "pg_enum", "tenant_indexes", "LTREE", "POINT",
    "BitluxBase", "IdMixin", "TimestampMixin", "AuthoredMixin",
    "TenantColumnMixin", "OptionalTenantColumnMixin", "TenantScopedMixin", "SharedCatalogMixin",
]


def uuid7() -> uuid.UUID:
    """Time-ordered UUIDv7 as a stdlib ``uuid.UUID``.

    Identifiers are generated here, never by PostgreSQL: PG16 has no native
    ``uuidv7()`` and the application needs the id before the INSERT (DATA_MODEL 1.5).
    ``uuid_utils`` returns its own UUID class; asyncpg wants the stdlib one.
    """
    return uuid.UUID(str(uuid_utils.uuid7()))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pg_enum(enum_cls: type[Enum]) -> ENUM:
    """Bind a Python enum from .enums to its existing PostgreSQL ENUM type.

    ``create_type=False`` because migration 002 owns the types; ``values_callable``
    persists the member *values* (the database labels) rather than member names.
    The type name comes from the enum's ``__pg_name__`` so it always matches
    migration 002 -- a mismatch here is what makes autogenerate try to recreate
    an enum.
    """
    return ENUM(
        enum_cls,
        name=enum_cls.__pg_name__,  # type: ignore[attr-defined]
        create_type=False,
        values_callable=lambda e: [m.value for m in e],
    )


class LTREE(UserDefinedType):
    """``ltree`` from the extension installed in migration 001 (segments.path)."""

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "ltree"


class POINT(UserDefinedType):
    """Core PostgreSQL ``point`` -- used instead of PostGIS geography (DATA_MODEL 1.6).

    Planar. Use it as an index prefilter only; compute real distances in Python.
    """

    cache_ok = True

    def get_col_spec(self, **kw: object) -> str:
        return "point"


def tenant_indexes(table: str) -> tuple[Index, Index, Index]:
    """The three standard indexes every tenant/catalog table carries (DATA_MODEL 1.1).

    Names match the migrations exactly so autogenerate sees no difference.
    """
    return (
        Index(f"ix_{table}_client", "client_id"),
        Index(f"ix_{table}_client_created", "client_id", text("created_at DESC")),
        Index(f"ix_{table}_client_live", "client_id", "id", postgresql_where=text("deleted_at IS NULL")),
    )


_UUID = UUID(as_uuid=True)
_TSTZ = TIMESTAMP(timezone=True)


class BitluxBase(SQLModel):
    """Common base for every table model.

    ``__repr__`` prints the class name and id only. Pydantic's default repr walks
    every field, and on an ORM instance that means touching relationship
    attributes -- an accidental N+1 every time an object lands in a log line.
    """

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={getattr(self, 'id', None)}>"

    __str__ = __repr__


class IdMixin(SQLModel):
    """UUIDv7 primary key supplied by the application; the database has no default."""

    id: uuid.UUID = Field(default_factory=uuid7, sa_type=_UUID, primary_key=True)


class TimestampMixin(SQLModel):
    """created_at / updated_at (trigger-maintained in the DB) / deleted_at (soft delete)."""

    created_at: datetime = Field(
        default_factory=utcnow, sa_type=_TSTZ, nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    updated_at: datetime = Field(
        default_factory=utcnow, sa_type=_TSTZ, nullable=False,
        sa_column_kwargs={"server_default": text("now()")},
    )
    deleted_at: Optional[datetime] = Field(default=None, sa_type=_TSTZ)


class AuthoredMixin(SQLModel):
    """Who wrote / last touched the row. SET NULL so deleting a user keeps the row."""

    created_by: Optional[uuid.UUID] = Field(
        default=None, sa_type=_UUID, foreign_key="users.id", ondelete="SET NULL"
    )
    updated_by: Optional[uuid.UUID] = Field(
        default=None, sa_type=_UUID, foreign_key="users.id", ondelete="SET NULL"
    )


class TenantColumnMixin(SQLModel):
    """``client_id`` NOT NULL -- ordinary tenant tables."""

    client_id: uuid.UUID = Field(
        sa_type=_UUID, foreign_key="clients.id", ondelete="RESTRICT", nullable=False
    )


class OptionalTenantColumnMixin(SQLModel):
    """``client_id`` nullable -- shared reference catalog (NULL = global row, DATA_MODEL 1.3)
    and ``audit_logs`` (NULL = platform-level event)."""

    client_id: Optional[uuid.UUID] = Field(
        default=None, sa_type=_UUID, foreign_key="clients.id", ondelete="RESTRICT"
    )


class TenantScopedMixin(IdMixin, TenantColumnMixin, TimestampMixin, AuthoredMixin):
    """The standard column block from DATA_MODEL.md 1.1: id, client_id, created_at,
    updated_at, deleted_at, created_by, updated_by. Every ordinary tenant table
    inherits this and declares none of those columns itself."""


class SharedCatalogMixin(IdMixin, OptionalTenantColumnMixin, TimestampMixin, AuthoredMixin):
    """Same block for the shared reference catalog, where ``client_id`` may be NULL."""
