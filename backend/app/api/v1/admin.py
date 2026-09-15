"""/admin -- users and the audit log."""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.api.v1._crud import ResourceSpec, install_crud
from app.deps import RequestContext, get_context, require_permission
from app.models import User
from app.models.enums import AuditAction, EntityType
from app.repositories import AuditLogRepository, UserRepository
from app.repositories.base import MAX_PAGE_SIZE
from app.schemas.admin import AuditLogList, AuditLogRead, UserCreate, UserList, UserRead, UserUpdate
from app.security.passwords import hash_password
from app.security.permissions import ROLE_PERMISSIONS

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- users ---------------------------------------------------------------------
class _UserCreate(UserCreate):
    pass


class _UserUpdate(UserUpdate):
    pass


users_router = APIRouter(prefix="/users")  # mounted under /admin below -> /admin/users


class UserLookup(BaseModel):
    id: uuid.UUID
    full_name: str
    role: str


@users_router.get("/lookup", response_model=list[UserLookup], summary="Active colleagues (id + name) for owner/assignee pickers")
async def users_lookup(ctx: RequestContext = Depends(get_context)) -> list[UserLookup]:
    """Any authenticated user may see who else is in their tenant by name -- it is
    what every owner / assignee dropdown needs -- without users.view, which
    exposes emails, roles and status changes. Registered before install_crud so
    the literal path wins over /{item_id}."""
    rows = await UserRepository(ctx.session).list(page_size=MAX_PAGE_SIZE, status="active", order_by=(User.full_name,))
    return [UserLookup(id=u.id, full_name=u.full_name, role=u.role.value if hasattr(u.role, "value") else str(u.role)) for u in rows]


def _hash_password_in(payload_cls):
    """UserCreate/UserUpdate carry a plaintext `password`; it must become password_hash before the repo."""
    orig_dump = payload_cls.model_dump

    def model_dump(self, *a, **kw):
        d = orig_dump(self, *a, **kw)
        pw = d.pop("password", None)
        if pw:
            d["password_hash"] = hash_password(pw)
        return d

    payload_cls.model_dump = model_dump
    return payload_cls


USER_SPEC = ResourceSpec(
    name="users", model=User, repo=UserRepository,
    create=_hash_password_in(_UserCreate), update=_hash_password_in(_UserUpdate), read=UserRead, list=UserList,
    graph_type="user", entity_type=EntityType.USER,
    filters=("role", "status", "email"), permission_prefix="users",
)
install_crud(users_router, USER_SPEC)


@router.get("/roles", summary="Role -> permission map")
async def roles(ctx: RequestContext = Depends(require_permission("users.view"))) -> dict[str, list[str]]:
    return {role.value: sorted(perms) for role, perms in ROLE_PERMISSIONS.items()}


# ---- audit log -------------------------------------------------------------------
@router.get("/audit-log", response_model=AuditLogList, summary="Audit trail (read-only)")
async def audit_log(
    entity_type: Optional[EntityType] = None,
    entity_id: Optional[uuid.UUID] = None,
    actor_user_id: Optional[uuid.UUID] = None,
    action: Optional[AuditAction] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
    ctx: RequestContext = Depends(require_permission("audit.view")),
) -> AuditLogList:
    repo = AuditLogRepository(ctx.session)
    equals = {k: v for k, v in dict(entity_type=entity_type, entity_id=entity_id, actor_user_id=actor_user_id, action=action).items() if v is not None}
    from app.models import AuditLog

    items = await repo.list(page=page, page_size=page_size, order_by=(AuditLog.occurred_at.desc(),), **equals)
    total = await repo.count(**equals)
    return AuditLogList(items=[AuditLogRead.model_validate(i) for i in items], total=total, page=page, page_size=page_size)


@router.get("/audit-log/{entity_type}/{entity_id}", response_model=list[AuditLogRead], summary="History of one record")
async def history(entity_type: EntityType, entity_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("audit.view"))) -> list[AuditLogRead]:
    return [AuditLogRead.model_validate(r) for r in await AuditLogRepository(ctx.session).history_of(entity_type, entity_id)]


router.include_router(users_router)
