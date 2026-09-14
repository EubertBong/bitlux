"""BaseRepository: the only way application code touches a table.

Every read goes through ``_base_query()``, which

  (a) filters ``deleted_at IS NULL`` -- soft delete is invisible by default, and
  (b) adds ``client_id = current_client_id()`` even though RLS already enforces
      it. RLS is the guarantee; this predicate is defence in depth, and it turns
      a missing tenant context into a Python exception instead of an empty
      result set.

Writes stamp ``id`` (UUIDv7), ``client_id``, ``created_by``/``updated_by`` from
the context so callers cannot forget them. Hard deletes are refused unless a
repository opts in; audit rows cannot be written here at all.
"""

from __future__ import annotations

import uuid
from typing import Any, ClassVar, Generic, Iterable, Optional, Sequence, TypeVar

from sqlalchemy import ColumnElement, Select, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import SQLModel

from app.models.base import utcnow, uuid7

from .context import current_client_id, current_user_id

__all__ = [
    "BaseRepository",
    "SharedCatalogRepository",
    "RepositoryError",
    "NotFound",
    "HardDeleteNotAllowed",
    "ImmutableModel",
    "MAX_PAGE_SIZE",
]

T = TypeVar("T", bound=SQLModel)
MAX_PAGE_SIZE = 500


class RepositoryError(Exception):
    """Base class for repository-level errors."""


class NotFound(RepositoryError):
    def __init__(self, model: type, id_: object) -> None:
        super().__init__(f"{model.__name__} {id_} not found (or soft-deleted, or another tenant's)")
        self.model, self.id = model, id_


class HardDeleteNotAllowed(RepositoryError):
    pass


class ImmutableModel(RepositoryError):
    pass


class BaseRepository(Generic[T]):
    """Generic CRUD with tenant scoping and soft delete baked in.

    Subclasses set ``model``. Set ``allow_hard_delete = True`` only for tables
    where a physical delete is a legitimate operation (DATA_MODEL 1.2 says:
    almost none). Set ``immutable = True`` for append-only tables.
    """

    model: ClassVar[type[Any]]
    allow_hard_delete: ClassVar[bool] = False
    immutable: ClassVar[bool] = False

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------ scoping
    @classmethod
    def _has(cls, column: str) -> bool:
        return column in cls.model.__table__.c

    def _tenant_predicate(self) -> ColumnElement[bool]:
        """client_id = current tenant. Raises TenantContextMissing if unset."""
        return self.model.client_id == current_client_id()

    def _live_predicate(self) -> ColumnElement[bool]:
        return self.model.deleted_at.is_(None) if self._has("deleted_at") else true()

    def _base_query(self) -> Select:
        return select(self.model).where(self._live_predicate(), self._tenant_predicate())

    def _default_order(self) -> Sequence[Any]:
        if self._has("created_at"):
            return (self.model.created_at.desc(), self.model.id)
        return (self.model.id,)

    def _apply(self, stmt: Select, criteria: Iterable[Any], equals: dict[str, Any]) -> Select:
        for c in criteria:
            stmt = stmt.where(c)
        for key, value in equals.items():
            stmt = stmt.where(getattr(self.model, key) == value)
        return stmt

    # -------------------------------------------------------------------- reads
    async def get(self, id_: uuid.UUID) -> Optional[T]:
        return (await self.session.execute(self._base_query().where(self.model.id == id_))).scalar_one_or_none()

    async def get_or_raise(self, id_: uuid.UUID) -> T:
        obj = await self.get(id_)
        if obj is None:
            raise NotFound(self.model, id_)
        return obj

    async def list(
        self,
        *criteria: Any,
        page: int = 1,
        page_size: int = 50,
        order_by: Optional[Sequence[Any]] = None,
        **equals: Any,
    ) -> list[T]:
        """Live, tenant-scoped rows, paginated (1-based)."""
        page = max(1, page)
        page_size = max(1, min(page_size, MAX_PAGE_SIZE))
        stmt = self._apply(self._base_query(), criteria, equals)
        stmt = stmt.order_by(*(order_by or self._default_order()))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        return list((await self.session.execute(stmt)).scalars().all())

    async def count(self, *criteria: Any, **equals: Any) -> int:
        stmt = self._apply(select(func.count()).select_from(self.model).where(self._live_predicate(), self._tenant_predicate()), criteria, equals)
        return int((await self.session.execute(stmt)).scalar_one())

    # ------------------------------------------------------------------- writes
    def _refuse_if_immutable(self) -> None:
        if self.immutable:
            raise ImmutableModel(f"{self.model.__name__} is append-only; use its repository's append().")

    async def create(self, data: dict[str, Any] | T) -> T:
        """Insert. Stamps id (UUIDv7), client_id, created_by, updated_by from context."""
        self._refuse_if_immutable()
        obj: T = self.model(**data) if isinstance(data, dict) else data
        if getattr(obj, "id", None) is None:
            obj.id = uuid7()
        if self._has("client_id") and getattr(obj, "client_id", None) is None:
            obj.client_id = current_client_id()
        if self._has("created_by"):
            actor = current_user_id()
            if getattr(obj, "created_by", None) is None:
                obj.created_by = actor
            obj.updated_by = actor
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def update(self, id_: uuid.UUID, data: dict[str, Any]) -> T:
        self._refuse_if_immutable()
        obj = await self.get_or_raise(id_)
        for key, value in data.items():
            if key in ("id", "client_id", "created_at", "created_by"):
                raise RepositoryError(f"{key} is not updatable")
            setattr(obj, key, value)
        if self._has("updated_by"):
            obj.updated_by = current_user_id()
        if self._has("updated_at"):
            obj.updated_at = utcnow()  # the DB trigger sets it too; keep the instance honest
        await self.session.flush()
        return obj

    async def soft_delete(self, id_: uuid.UUID) -> T:
        """Tombstone the row. It disappears from every repository read; the row stays."""
        self._refuse_if_immutable()
        if not self._has("deleted_at"):
            raise RepositoryError(f"{self.model.__name__} has no deleted_at; nothing to soft-delete")
        obj = await self.get_or_raise(id_)
        obj.deleted_at = utcnow()
        if self._has("updated_by"):
            obj.updated_by = current_user_id()
        await self.session.flush()
        return obj

    async def restore(self, id_: uuid.UUID) -> T:
        """Undo a soft delete. Bypasses the live filter on purpose."""
        self._refuse_if_immutable()
        stmt = select(self.model).where(self.model.id == id_, self._tenant_predicate())
        obj = (await self.session.execute(stmt)).scalar_one_or_none()
        if obj is None:
            raise NotFound(self.model, id_)
        obj.deleted_at = None
        await self.session.flush()
        return obj

    async def hard_delete(self, id_: uuid.UUID) -> None:
        """Physically delete. Refused unless the repository opts in."""
        self._refuse_if_immutable()
        if not self.allow_hard_delete:
            raise HardDeleteNotAllowed(
                f"{self.model.__name__} does not allow hard deletes; use soft_delete()."
            )
        obj = await self.get_or_raise(id_)
        await self.session.delete(obj)
        await self.session.flush()


class SharedCatalogRepository(BaseRepository[T]):
    """For manufacturers / aircraft_models / airports / fbos (DATA_MODEL 1.3).

    Reads see global rows (``client_id IS NULL``) plus the tenant's own; creates
    are always tenant-private. Writing a global row is a platform operation,
    not something the application does.
    """

    def _tenant_predicate(self) -> ColumnElement[bool]:
        return or_(self.model.client_id.is_(None), self.model.client_id == current_client_id())
