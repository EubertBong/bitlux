"""Dependency injection: the database session, the authenticated user, the
permission check. Every protected route depends on ``require_permission(key)``,
which yields a RequestContext with the session already inside a tenant
transaction (DATA_MODEL.md 1.7 -- RLS is live from the first query).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Callable

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import get_settings
from app.errors import PermissionDenied, Unauthorized
from app.models import User
from app.models.enums import UserStatus
from app.repositories import UserRepository, tenant_transaction
from app.security.permissions import has_permission, permissions_for
from app.security.tokens import Claims, TokenError, decode

_engine: AsyncEngine | None = None
_sessions: async_sessionmaker[AsyncSession] | None = None


def engine() -> AsyncEngine:
    global _engine, _sessions
    if _engine is None:
        s = get_settings()
        _engine = create_async_engine(s.database_url, pool_size=s.db_pool_size, echo=s.db_echo, pool_pre_ping=True)
        _sessions = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


async def dispose_engine() -> None:
    global _engine, _sessions
    if _engine is not None:
        await _engine.dispose()
    _engine = _sessions = None


async def get_session() -> AsyncIterator[AsyncSession]:
    """A session per request. Tests override this to inject a rolled-back one."""
    engine()
    assert _sessions is not None
    async with _sessions() as session:
        yield session


_bearer = HTTPBearer(auto_error=False)


def get_claims(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> Claims:
    if creds is None or creds.scheme.lower() != "bearer":
        raise Unauthorized("Authentication required")
    try:
        return decode(creds.credentials, "access")
    except TokenError as e:
        raise Unauthorized(str(e)) from e


async def get_tenant_session(
    request: Request, claims: Claims = Depends(get_claims), session: AsyncSession = Depends(get_session)
) -> AsyncIterator[AsyncSession]:
    """The request's session, inside tenant_transaction() for the token's tenant."""
    request.state.user_id = str(claims.user_id)
    request.state.client_id = str(claims.client_id)
    async with tenant_transaction(session, claims.client_id, claims.user_id):
        yield session


@dataclass
class RequestContext:
    session: AsyncSession
    user: User
    claims: Claims
    permissions: frozenset[str]

    def can(self, key: str) -> bool:
        return has_permission(self.user.role, key)

    @property
    def actor_label(self) -> str:
        return f"{self.user.full_name} <{self.user.email}>"


async def get_context(claims: Claims = Depends(get_claims), session: AsyncSession = Depends(get_tenant_session)) -> RequestContext:
    """Loads the user *under RLS* (so a token for another tenant finds nothing) and
    takes the role from the row, not the token: a demotion is effective immediately."""
    user = await UserRepository(session).get(claims.user_id)
    if user is None or user.status != UserStatus.ACTIVE:
        raise Unauthorized("User is not active")
    return RequestContext(session=session, user=user, claims=claims, permissions=permissions_for(user.role))


def require_permission(key: str) -> Callable[..., RequestContext]:
    """Dependency factory: ``ctx = Depends(require_permission("contacts.create"))``."""

    async def _check(ctx: RequestContext = Depends(get_context)) -> RequestContext:
        if not ctx.can(key):
            raise PermissionDenied(
                f"Your role ({ctx.user.role.value}) does not include the '{key}' permission",
                details={"required": key, "role": ctx.user.role.value},
            )
        return ctx

    _check.__name__ = f"require_{key.replace('.', '_')}"
    return _check
