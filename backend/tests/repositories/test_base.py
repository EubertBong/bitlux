"""BaseRepository contract: soft delete, tenant scope, stamping, immutability."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Contact, Tag
from app.models.enums import AuditAction, EntityType
from app.repositories import (
    AuditEvent,
    AuditLogRepository,
    ClientRepository,
    ContactRepository,
    HardDeleteNotAllowed,
    ImmutableModel,
    TagRepository,
    TenantContextMissing,
    tenant_transaction,
)


async def test_get_respects_soft_delete(session):
    tags = TagRepository(session)
    tag = await tags.create({"name": "temp-soft-delete"})
    assert await tags.get(tag.id) is not None

    await tags.soft_delete(tag.id)

    assert await tags.get(tag.id) is None, "a soft-deleted row must be invisible to get()"
    assert all(t.id != tag.id for t in await tags.list(page_size=500))
    # ...and can come back.
    await tags.restore(tag.id)
    assert await tags.get(tag.id) is not None


async def test_soft_delete_does_not_hard_delete(session):
    tags = TagRepository(session)
    tag = await tags.create({"name": "temp-tombstone"})
    await tags.soft_delete(tag.id)

    row = (await session.execute(select(Tag.deleted_at).where(Tag.id == tag.id))).one()
    assert row.deleted_at is not None, "the row must still exist, with a tombstone"

    with pytest.raises(HardDeleteNotAllowed):
        await tags.hard_delete(tag.id)


async def test_create_sets_id_and_created_by(session, demo_id, broker_id):
    tag = await TagRepository(session).create({"name": "temp-stamped"})
    assert tag.id.version == 7, "ids are application-generated UUIDv7 (DATA_MODEL 1.5)"
    assert tag.client_id == demo_id
    assert tag.created_by == broker_id
    assert tag.updated_by == broker_id


async def test_list_respects_tenant_scope(session, demo_id):
    """Two tenants in one transaction; each sees only its own rows -- under RLS."""
    contacts = ContactRepository(session)
    other = uuid.uuid5(demo_id, "tenant-b")

    async with tenant_transaction(session, other, None):
        await ClientRepository(session).create({"id": other, "slug": "tenant-b", "name": "Tenant B"})
        await contacts.create({"display_name": "B Only", "last_name": "Only"})
        assert [c.display_name for c in await contacts.list()] == ["B Only"]

    # back in the demo tenant
    names = {c.display_name for c in await contacts.list(page_size=500)}
    assert "B Only" not in names
    assert await contacts.count() == 8


async def test_tenant_isolation_no_cross_read(session, demo_id):
    """Even if Python's context were wrong, the database side wins."""
    contacts = ContactRepository(session)
    assert await contacts.count() == 8

    # Point PostgreSQL at another tenant while Python still thinks it is the demo tenant.
    await session.execute(text("SELECT set_config('app.client_id', :cid, true)"), {"cid": str(uuid.uuid4())})
    assert await contacts.list() == []
    assert (await session.execute(select(func.count()).select_from(Contact))).scalar_one() == 0
    await session.execute(text("SELECT set_config('app.client_id', :cid, true)"), {"cid": str(demo_id)})
    assert await contacts.count() == 8


async def test_missing_tenant_context_fails_closed(bare_session):
    with pytest.raises(TenantContextMissing):
        await ContactRepository(bare_session).list()


async def test_audit_append_is_immutable(session, demo_id):
    audit = AuditLogRepository(session)
    new_id = await audit.append(AuditEvent(
        action=AuditAction.UPDATE, entity_type=EntityType.CONTACT, entity_id=uuid.uuid4(),
        entity_label="Test Contact", actor_label="Ben Carter <broker@demo.test>",
        changed_fields=["status"], before={"status": "lead"}, after={"status": "active"},
    ))
    history = await audit.history_of(EntityType.CONTACT, (await audit.get(new_id)).entity_id)
    assert [h.id for h in history] == [new_id]
    assert history[0].client_id == demo_id

    # The repository refuses every mutation path.
    with pytest.raises(ImmutableModel):
        await audit.update(new_id, {"reason": "tampering"})
    with pytest.raises(ImmutableModel):
        await audit.soft_delete(new_id)
    with pytest.raises(ImmutableModel):
        await audit.create({"actor_label": "x"})

    # PostgreSQL refuses a raw UPDATE (no privilege, and the trigger). A failed
    # statement poisons its transaction, so it runs in a savepoint.
    with pytest.raises(DBAPIError):
        async with session.begin_nested():
            await session.execute(update(AuditLog.__table__).where(AuditLog.__table__.c.id == new_id).values(reason="x"))

    # The ORM refuses a dirty flush. A failed flush poisons the *session* by design
    # (it must be rolled back), so this runs in a throwaway session on the same
    # connection -- same tenant, same rolled-back outer transaction.
    scratch = AsyncSession(bind=session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint")
    try:
        row = (await scratch.execute(select(AuditLog).where(AuditLog.id == new_id))).scalar_one()
        row.reason = "tampering"
        with pytest.raises(PermissionError):
            await scratch.flush()
        await scratch.rollback()
    finally:
        await scratch.close()
    assert (await audit.get(new_id)).reason is None, "nothing got through"
