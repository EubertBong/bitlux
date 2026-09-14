"""Test fixtures: every test runs as bitlux_app (RLS enforced), inside a
transaction that is rolled back at the end, against the seeded demo tenant.

Connecting as the application role is the whole point: as ``bitlux`` (superuser)
RLS is bypassed and an isolation test proves nothing (DATA_MODEL.md 1.7).
"""

from __future__ import annotations

import os
import pathlib
import sys
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.repositories import tenant_transaction

# The seed module is the source of truth for demo ids (uuid5 of natural keys).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))
from seed import DEMO, u  # noqa: E402

APP_DATABASE_URL = os.getenv(
    "APP_DATABASE_URL", "postgresql+asyncpg://bitlux_app:bitlux_app@localhost:5433/bitlux_crm"
)

BROKER = u("user:broker@demo.test")
OPS = u("user:ops@demo.test")
OWNER = u("user:owner@demo.test")


@pytest.fixture
def demo_id() -> uuid.UUID:
    return DEMO


@pytest.fixture
def broker_id() -> uuid.UUID:
    return BROKER


@pytest.fixture
def seed_id():
    """Deterministic id of any seeded row, by its natural key: seed_id('trip:t1')."""
    return u


@pytest.fixture
async def connection():
    engine = create_async_engine(APP_DATABASE_URL, poolclass=NullPool)
    async with engine.connect() as conn:
        outer = await conn.begin()
        try:
            yield conn
        finally:
            await outer.rollback()  # nothing a test does survives it
    await engine.dispose()


@pytest.fixture
async def bare_session(connection):
    """A session on the rolled-back connection, with NO tenant context."""
    session = AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()


@pytest.fixture
async def session(bare_session):
    """The usual case: the demo tenant, acting as the broker user."""
    async with tenant_transaction(bare_session, DEMO, BROKER):
        yield bare_session
