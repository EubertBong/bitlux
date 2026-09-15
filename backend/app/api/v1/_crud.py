"""The standard six operations for every resource, built once.

    GET    /{resource}                    list: page, page_size, order_by, ?<filter>=, ?q= (full text, when searchable)
    GET    /{resource}/{id}               get (soft-deleted -> 404)
    POST   /{resource}                    create   (<prefix>.create, or an override)
    PATCH  /{resource}/{id}               update   (<prefix>.edit)
    DELETE /{resource}/{id}               soft delete (<prefix>.delete)
    POST   /{resource}/{id}/restore       undo a soft delete (<prefix>.delete)
    GET    /{resource}/{id}/relationships depth-1 neighbourhood (<prefix>.view)

Every mutation appends an audit event (redacted) when the resource is an
EntityType. Plaintext values for [enc] columns are encrypted here and never
travel further.

No ``from __future__ import annotations`` in this module: the endpoint closures
annotate parameters with schema classes held in local variables, which FastAPI
must be able to evaluate.
"""

import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Optional, Type

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy import Float, column, func, literal
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from pydantic import BaseModel

from app.deps import RequestContext, require_permission
from app.errors import ApiError
from app.models.enums import AuditAction, EntityType
from app.repositories import AuditEvent, AuditLogRepository, GraphResolver
from app.repositories.base import MAX_PAGE_SIZE, BaseRepository
from app.repositories.graph import GRAPH_TYPES
from app.repositories.search import SEARCH_TYPES, _tsquery
from app.schemas.common import GraphResponse
from app.security.crypto import ENCRYPTED_FIELDS, encrypt, last4, redact


class Unprocessable(ApiError):
    """Bad query parameter."""
    status_code, code = status.HTTP_422_UNPROCESSABLE_ENTITY, "validation_error"


@dataclass
class ResourceSpec:
    name: str
    model: Type[Any]
    repo: Type[BaseRepository]
    create: Type[BaseModel]
    update: Type[BaseModel]
    read: Type[BaseModel]
    list: Type[BaseModel]
    graph_type: str
    entity_type: Optional[EntityType] = None
    filters: tuple[str, ...] = ()
    permission_prefix: str = ""
    create_permission: Optional[str] = None
    encrypted_inputs: tuple[str, ...] = ()
    orderable: tuple[str, ...] = field(default_factory=tuple)
    #: Key into repositories.search.SEARCH_TYPES; enables ?q= on the list endpoint.
    search_type: Optional[str] = None

    def __post_init__(self) -> None:
        self.permission_prefix = self.permission_prefix or self.name
        if not self.orderable:
            self.orderable = tuple(c.name for c in self.model.__table__.c if c.name not in ("search_tsv", "ocr_tsv", "location"))

    def perm(self, action: str) -> str:
        if action == "create" and self.create_permission:
            return self.create_permission
        return f"{self.permission_prefix}.{action}"


# --------------------------------------------------------------- conversions
def _coerce(model: Type[Any], key: str, raw: str) -> Any:
    col = model.__table__.c.get(key)
    if col is None:
        raise Unprocessable(f"Unknown filter '{key}'")
    t = col.type
    try:
        if isinstance(t, sa.Boolean):
            if raw.lower() in ("true", "1", "yes"):
                return True
            if raw.lower() in ("false", "0", "no"):
                return False
            raise ValueError(raw)
        if isinstance(t, sa.dialects.postgresql.UUID):
            return uuid.UUID(raw)
        if isinstance(t, sa.Integer):
            return int(raw)
        if isinstance(t, sa.dialects.postgresql.ENUM):
            if raw not in t.enums:
                raise ValueError(f"must be one of {t.enums}")
            return raw
        return raw
    except ValueError as e:
        raise Unprocessable(f"Invalid value for filter '{key}': {e}") from e


def to_repo_payload(spec: ResourceSpec, data: dict[str, Any]) -> dict[str, Any]:
    """Schema dict -> repository dict: encrypt [enc] inputs, Decimal for Numeric columns."""
    out: dict[str, Any] = {}
    cols = spec.model.__table__.c
    for key, value in data.items():
        if key in spec.encrypted_inputs:
            if value is None:
                continue
            out[key] = encrypt(value)
            l4 = ENCRYPTED_FIELDS.get(key)
            if l4 and l4 in cols:
                out[l4] = last4(value)
            continue
        col = cols.get(key)
        if col is not None and isinstance(col.type, sa.Numeric) and isinstance(value, float):
            value = Decimal(str(value))
        out[key] = value
    return out


_SEARCH_LIST_LIMIT = 1000


def _search_criterion(spec: ResourceSpec, q: str):
    """``model.id IN (SELECT id FROM search_ids(type, tsquery, N))`` -- the same
    SECURITY DEFINER path /search uses (migration 017), so the GIN index is usable
    under RLS; the outer statement is still under RLS and the live filter."""
    if not spec.search_type or spec.search_type not in SEARCH_TYPES:
        raise Unprocessable(f"'{spec.name}' is not searchable")
    st = SEARCH_TYPES[spec.search_type]
    hit = (
        func.search_ids(literal(spec.search_type), _tsquery(q, st.config), literal(_SEARCH_LIST_LIMIT, sa.Integer))
        .table_valued(column("id", PG_UUID(as_uuid=True)), column("rank", Float))
        .render_derived()
        .alias("hit")
    )
    return spec.model.id.in_(sa.select(hit.c.id))


def _label(spec: ResourceSpec, obj: Any) -> Optional[str]:
    t = GRAPH_TYPES.get(spec.graph_type)
    try:
        return t.label(obj) if t else None
    except Exception:  # presentation must never break a write
        return None


async def _audit(ctx: RequestContext, spec: ResourceSpec, action: AuditAction, obj: Any,
                 before: Optional[dict] = None, after: Optional[dict] = None, changed: Optional[list[str]] = None) -> None:
    if spec.entity_type is None:
        return
    await AuditLogRepository(ctx.session).append(AuditEvent(
        action=action, entity_type=spec.entity_type, entity_id=obj.id, entity_label=_label(spec, obj),
        actor_label=ctx.actor_label, changed_fields=changed, before=redact(before), after=redact(after),
        request_id=_request_id(ctx),
    ))


def _request_id(ctx: RequestContext) -> Optional[uuid.UUID]:
    return None  # populated from request.state by the endpoints that have the Request


def _snapshot(spec: ResourceSpec, obj: Any) -> dict[str, Any]:
    """JSON-safe view of a row for the audit trail (encrypted columns dropped)."""
    out = {}
    for c in spec.model.__table__.c:
        if c.name in ENCRYPTED_FIELDS or c.name in ("search_tsv", "ocr_tsv", "location", "password_hash", "token_hash"):
            continue
        v = getattr(obj, "metadata_" if c.name == "metadata" else c.name, None)
        out[c.name] = v if isinstance(v, (str, int, float, bool, type(None), list, dict)) else str(v)
    return out


# ---------------------------------------------------------------- the routes
def install_crud(router: APIRouter, spec: ResourceSpec) -> None:
    Create, Update, Read, ListOut = spec.create, spec.update, spec.read, spec.list
    view = require_permission(spec.perm("view"))
    create_perm = require_permission(spec.perm("create"))
    edit = require_permission(spec.perm("edit"))
    delete = require_permission(spec.perm("delete"))

    @router.get("", response_model=ListOut, summary=f"List {spec.name}",
                description=f"Filters (equality): {', '.join(spec.filters) or 'none'}. order_by accepts a column name, '-' prefix for descending."
                            + (" q= runs full-text search (websearch syntax + prefix on the last word)." if spec.search_type else ""))
    async def list_items(
        request: Request,
        page: int = Query(1, ge=1),
        page_size: int = Query(50, ge=1, le=MAX_PAGE_SIZE),
        order_by: Optional[str] = Query(None, description="e.g. -created_at"),
        q: Optional[str] = Query(None, description="Full-text search (searchable resources only)"),
        ctx: RequestContext = Depends(view),
    ):
        repo = spec.repo(ctx.session)
        equals = {}
        for key in spec.filters:
            if key in request.query_params:
                equals[key] = _coerce(spec.model, key, request.query_params[key])
        criteria = [_search_criterion(spec, q)] if q and q.strip() else []
        ordering = None
        if order_by:
            col_name = order_by.lstrip("-")
            if col_name not in spec.orderable:
                raise Unprocessable(f"Cannot order by '{col_name}'")
            col = getattr(spec.model, col_name)
            ordering = (col.desc().nulls_last() if order_by.startswith("-") else col.asc().nulls_last(), spec.model.id)
        items = await repo.list(*criteria, page=page, page_size=page_size, order_by=ordering, **equals)
        total = await repo.count(*criteria, **equals)
        return ListOut(items=[Read.model_validate(i) for i in items], total=total, page=page, page_size=page_size)

    @router.get("/{item_id}", response_model=Read, summary=f"Get one of {spec.name}")
    async def get_item(item_id: uuid.UUID, ctx: RequestContext = Depends(view)):
        return Read.model_validate(await spec.repo(ctx.session).get_or_raise(item_id))

    @router.post("", response_model=Read, status_code=status.HTTP_201_CREATED, summary=f"Create {spec.name}")
    async def create_item(payload: Create, request: Request, ctx: RequestContext = Depends(create_perm)):  # type: ignore[valid-type]
        data = to_repo_payload(spec, payload.model_dump(by_alias=False))
        obj = await spec.repo(ctx.session).create(data)
        await _audit(ctx, spec, AuditAction.INSERT, obj, after=_snapshot(spec, obj))
        return Read.model_validate(obj)

    @router.patch("/{item_id}", response_model=Read, summary=f"Update {spec.name}")
    async def update_item(item_id: uuid.UUID, payload: Update, ctx: RequestContext = Depends(edit)):  # type: ignore[valid-type]
        repo = spec.repo(ctx.session)
        before_obj = await repo.get_or_raise(item_id)
        before = _snapshot(spec, before_obj)
        data = to_repo_payload(spec, payload.model_dump(exclude_unset=True, by_alias=False))
        if not data:
            raise Unprocessable("No fields to update")
        obj = await repo.update(item_id, data)
        after = _snapshot(spec, obj)
        changed = sorted(k for k in after if before.get(k) != after.get(k) and k not in ("updated_at", "updated_by"))
        await _audit(ctx, spec, AuditAction.UPDATE, obj, before={k: before[k] for k in changed}, after={k: after[k] for k in changed}, changed=changed)
        return Read.model_validate(obj)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary=f"Soft-delete {spec.name}")
    async def delete_item(item_id: uuid.UUID, ctx: RequestContext = Depends(delete)):
        obj = await spec.repo(ctx.session).soft_delete(item_id)
        await _audit(ctx, spec, AuditAction.SOFT_DELETE, obj, before=_snapshot(spec, obj))
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    @router.post("/{item_id}/restore", response_model=Read, summary=f"Restore a soft-deleted one of {spec.name}")
    async def restore_item(item_id: uuid.UUID, ctx: RequestContext = Depends(delete)):
        """Undo of DELETE. Same permission as delete; audited as `restore`."""
        obj = await spec.repo(ctx.session).restore(item_id)
        await _audit(ctx, spec, AuditAction.RESTORE, obj, after=_snapshot(spec, obj))
        return Read.model_validate(obj)

    @router.get("/{item_id}/relationships", response_model=GraphResponse, summary=f"Neighbourhood of one of {spec.name}")
    async def relationships(item_id: uuid.UUID, ctx: RequestContext = Depends(view)):
        resolver = GraphResolver(ctx.session, can_view=ctx.can)
        return await resolver.neighbourhood(spec.graph_type, item_id, depth=1)


# ------------------------------------------------------------ nested resources
async def create_child(ctx: RequestContext, spec: ResourceSpec, payload: BaseModel, **fixed: Any) -> Any:
    """Create a child row with parent ids fixed by the URL, with encryption + audit as usual."""
    data = to_repo_payload(spec, payload.model_dump(by_alias=False))
    data.update(fixed)
    obj = await spec.repo(ctx.session).create(data)
    await _audit(ctx, spec, AuditAction.INSERT, obj, after=_snapshot(spec, obj))
    return spec.read.model_validate(obj)


async def list_children(ctx: RequestContext, spec: ResourceSpec, order_by: Any = None, **equals: Any) -> list[Any]:
    rows = await spec.repo(ctx.session).list(page_size=MAX_PAGE_SIZE, order_by=order_by, **equals)
    return [spec.read.model_validate(r) for r in rows]
