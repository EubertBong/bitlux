"""Who is acting, for which tenant -- and how that reaches PostgreSQL.

Two halves that must always agree:

* **Python side** -- ``contextvars`` holding the current client, user and actor
  type. Repositories read these to stamp ``client_id``/``created_by`` and, as
  defence in depth, to add ``client_id = <tenant>`` to every query.
* **Database side** -- ``app.client_id`` / ``app.user_id`` set *for the current
  transaction only*, which is what the RLS policies (migration 014) key on.

``tenant_transaction()`` is the one place both are set together. Using it is
not optional: a session that never entered it has ``current_client_id()``
raising in Python and ``current_client_id()`` returning NULL in SQL, so every
query fails closed on both sides (DATA_MODEL.md 1.7).
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from typing import AsyncIterator, Iterator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import ActorType

__all__ = [
    "TenantContextMissing",
    "current_client_id",
    "current_client_id_or_none",
    "current_user_id",
    "current_actor_type",
    "tenant_context",
    "tenant_transaction",
]

_client_id: ContextVar[Optional[uuid.UUID]] = ContextVar("bitlux_client_id", default=None)
_user_id: ContextVar[Optional[uuid.UUID]] = ContextVar("bitlux_user_id", default=None)
_actor_type: ContextVar[ActorType] = ContextVar("bitlux_actor_type", default=ActorType.SYSTEM)


class TenantContextMissing(RuntimeError):
    """Raised when data access is attempted with no tenant in context.

    Deliberately an error rather than "no rows": a query that silently returns
    nothing hides a missing ``tenant_transaction()`` until production.
    """


def current_client_id() -> uuid.UUID:
    cid = _client_id.get()
    if cid is None:
        raise TenantContextMissing(
            "No tenant in context. Wrap data access in "
            "`async with tenant_transaction(session, client_id, user_id): ...`."
        )
    return cid


def current_client_id_or_none() -> Optional[uuid.UUID]:
    return _client_id.get()


def current_user_id() -> Optional[uuid.UUID]:
    """The acting user, or None for system/integration actors."""
    return _user_id.get()


def current_actor_type() -> ActorType:
    return _actor_type.get()


@contextmanager
def tenant_context(
    client_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    actor_type: ActorType = ActorType.USER,
) -> Iterator[None]:
    """Bind the Python-side context only. Prefer ``tenant_transaction``; this
    exists for code paths that already hold a correctly configured transaction."""
    tokens = (_client_id.set(client_id), _user_id.set(user_id), _actor_type.set(actor_type))
    try:
        yield
    finally:
        _client_id.reset(tokens[0])
        _user_id.reset(tokens[1])
        _actor_type.reset(tokens[2])


_depth: ContextVar[int] = ContextVar("bitlux_tenant_depth", default=0)


@asynccontextmanager
async def tenant_transaction(
    session: AsyncSession,
    client_id: uuid.UUID,
    user_id: Optional[uuid.UUID] = None,
    actor_type: ActorType = ActorType.USER,
) -> AsyncIterator[AsyncSession]:
    """Run a block inside a transaction that knows its tenant, on both sides.

    * The **outermost** call owns the transaction: it uses the one already open
      on the session (SQLAlchemy autobegins on the first statement -- a login
      lookup, say) or begins one, sets ``app.client_id`` / ``app.user_id`` for
      it, and **commits on normal exit, rolls back on exception**. Nesting is
      tracked explicitly, not inferred from ``session.in_transaction()``: an
      autobegun transaction looked like "someone else's" and was left
      uncommitted, so every login silently rolled back on session close.
    * A **nested** call (inside another ``tenant_transaction``) runs in a
      SAVEPOINT and restores the outer tenant's settings on exit, because
      ``set_config(..., is_local => true)`` is transaction-scoped, not
      savepoint-scoped.
    * ``set_config(name, value, is_local => true)`` is the parameterisable
      spelling of ``SET LOCAL``: same transaction scope, same reset on
      COMMIT/ROLLBACK, but it accepts bind parameters, which ``SET`` does not.
      Transaction scope is what makes this safe under connection pooling.
    * Binds the Python contextvars for the duration of the block.
    """
    depth = _depth.get()
    token = _depth.set(depth + 1)
    try:
        with tenant_context(client_id, user_id, actor_type):
            if depth == 0:
                if not session.in_transaction():
                    await session.begin()
                try:
                    await _set_tenant(session, client_id, user_id)
                    yield session
                except BaseException:
                    await session.rollback()
                    raise
                else:
                    await session.commit()
            else:
                previous = tuple((await session.execute(text(
                    "SELECT coalesce(current_setting('app.client_id', true), ''), "
                    "       coalesce(current_setting('app.user_id', true), '')"
                ))).one())
                try:
                    async with session.begin_nested():
                        await _set_tenant(session, client_id, user_id)
                        yield session
                finally:
                    if session.in_transaction():
                        await session.execute(
                            text("SELECT set_config('app.client_id', :cid, true), set_config('app.user_id', :uid, true)"),
                            {"cid": previous[0], "uid": previous[1]},
                        )
    finally:
        _depth.reset(token)


async def _set_tenant(session: AsyncSession, client_id: uuid.UUID, user_id: Optional[uuid.UUID]) -> None:
    await session.execute(text("SELECT set_config('app.client_id', :cid, true)"), {"cid": str(client_id)})
    await session.execute(text("SELECT set_config('app.user_id', :uid, true)"), {"uid": str(user_id) if user_id else ""})
