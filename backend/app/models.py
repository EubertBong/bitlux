"""SQLModel ORM models for the Bitlux CRM.

Currently a placeholder. ``alembic/env.py`` imports this module so that every
model registers itself on ``SQLModel.metadata``, which is what ``target_metadata``
points at for future ``--autogenerate`` support.

The schema itself is defined by the hand-written migrations in
``alembic/versions/001_*`` .. ``015_*``, generated from ``DATA_MODEL.md``. Those
migrations are authoritative today; the ORM models will be written to match them.

**Do not run ``alembic revision --autogenerate`` until the models below actually
cover the schema.** ``env.py`` raises if you try while this metadata is empty,
because the resulting diff would be "drop every table".

When adding models, follow DATA_MODEL.md 1.1 and 1.5:

    import uuid
    import uuid_utils
    from datetime import datetime
    from sqlmodel import Field, SQLModel

    def uuid7() -> uuid.UUID:
        # uuid_utils returns its own UUID class; asyncpg wants the stdlib one.
        return uuid.UUID(str(uuid_utils.uuid7()))

    class Contact(SQLModel, table=True):
        __tablename__ = "contacts"
        # No DB-side default: the application always supplies the id (DATA_MODEL 1.5).
        id: uuid.UUID = Field(default_factory=uuid7, primary_key=True)
        client_id: uuid.UUID = Field(foreign_key="clients.id", index=True)
        ...
"""

from __future__ import annotations

import uuid

import uuid_utils
from sqlmodel import SQLModel

__all__ = ["SQLModel", "uuid7"]


def uuid7() -> uuid.UUID:
    """Return a time-ordered UUIDv7 as a stdlib ``uuid.UUID``.

    Identifiers are generated here rather than by PostgreSQL: PG16 has no native
    ``uuidv7()`` and the application needs the id before the INSERT. See
    DATA_MODEL.md 1.5 for the full rationale.
    """
    return uuid.UUID(str(uuid_utils.uuid7()))
