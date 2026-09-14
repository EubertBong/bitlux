"""Users and refresh tokens, for the auth flow."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import text

from app.models import RefreshToken, User
from app.models.base import utcnow
from app.models.enums import ClientStatus, UserRole, UserStatus

from .base import BaseRepository

__all__ = ["UserRepository", "RefreshTokenRepository", "LoginCandidate"]


class LoginCandidate:
    """One row from auth_lookup_user() -- the only cross-tenant read (migration 016).

    The function returns raw SQL, and asyncpg hands PostgreSQL enums back as plain
    strings, so the three enum columns are coerced to their Python enums here --
    callers can use ``.value`` and compare against members like everywhere else.
    """

    __slots__ = ("user_id", "client_id", "client_slug", "role", "status", "client_status", "password_hash")
    _ENUMS = {"role": UserRole, "status": UserStatus, "client_status": ClientStatus}

    def __init__(self, row) -> None:
        for k in self.__slots__:
            v = row[k]
            if k in self._ENUMS and v is not None:
                v = self._ENUMS[k](v)
            setattr(self, k, v)


class UserRepository(BaseRepository[User]):
    model = User

    async def by_email(self, email: str) -> Optional[User]:
        return (await self.session.execute(self._base_query().where(User.email == email))).scalar_one_or_none()

    async def login_candidates(self, email: str, client_slug: str | None = None) -> list[LoginCandidate]:
        """Pre-tenant lookup by email via the SECURITY DEFINER function. Needs no
        tenant context -- it is what establishes one."""
        rows = await self.session.execute(
            text("SELECT * FROM auth_lookup_user(:email, :slug)"), {"email": email, "slug": client_slug}
        )
        return [LoginCandidate(r._mapping) for r in rows]

    async def touch_login(self, user_id: uuid.UUID) -> None:
        await self.update(user_id, {"last_login_at": utcnow()})


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    model = RefreshToken

    async def by_hash(self, token_hash: str) -> Optional[RefreshToken]:
        return (await self.session.execute(self._base_query().where(RefreshToken.token_hash == token_hash))).scalar_one_or_none()

    async def revoke(self, token_id: uuid.UUID, replaced_by: uuid.UUID | None = None) -> RefreshToken:
        return await self.update(token_id, {"revoked_at": utcnow(), "replaced_by_id": replaced_by})

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> int:
        live = await self.list(RefreshToken.revoked_at.is_(None), user_id=user_id, page_size=500)
        for tok in live:
            tok.revoked_at = utcnow()
        await self.session.flush()
        return len(live)
