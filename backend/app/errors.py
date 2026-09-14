"""One error shape for the whole API:

    {"error": {"code": "not_found", "message": "Contact not found", "details": {...}}}

Application exceptions subclass ApiError. install_exception_handlers() maps the
repository layer's exceptions, validation errors and anything unexpected onto
the same shape; unexpected errors carry the request id and nothing else.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError, IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.repositories.base import HardDeleteNotAllowed, ImmutableModel, NotFound, RepositoryError
from app.repositories.context import TenantContextMissing
from app.repositories.graph import GraphTooLarge, UnknownGraphType
from app.repositories.polymorphic import EntityNotFound
from app.security.tokens import TokenError

log = logging.getLogger("bitlux.api")


class ApiError(Exception):
    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"

    def __init__(self, message: str | None = None, *, details: dict[str, Any] | None = None, code: str | None = None) -> None:
        self.message = message or self.__class__.__doc__ or self.code
        self.details = details or {}
        if code:
            self.code = code
        super().__init__(self.message)


class Unauthorized(ApiError):
    """Authentication required."""
    status_code, code = status.HTTP_401_UNAUTHORIZED, "unauthorized"


class PermissionDenied(ApiError):
    """You do not have permission to do that."""
    status_code, code = status.HTTP_403_FORBIDDEN, "permission_denied"


class TenantMismatch(ApiError):
    """The request references a tenant other than the one you are acting as."""
    status_code, code = status.HTTP_403_FORBIDDEN, "tenant_mismatch"


class NotFoundError(ApiError):
    """Not found."""
    status_code, code = status.HTTP_404_NOT_FOUND, "not_found"


class Conflict(ApiError):
    """Conflict."""
    status_code, code = status.HTTP_409_CONFLICT, "conflict"


def _body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def _response(request: Request, status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    resp = JSONResponse(status_code=status_code, content=_body(code, message, details))
    if rid:
        resp.headers["X-Request-ID"] = rid
    return resp


def install_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(request: Request, exc: ApiError):
        return _response(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(NotFound)
    async def _repo_not_found(request: Request, exc: NotFound):
        # Covers "another tenant's row" too: RLS makes it indistinguishable from
        # non-existence, which is the point -- nothing about existence leaks.
        return _response(request, 404, "not_found", f"{exc.model.__name__} not found", {"id": str(exc.id)})

    @app.exception_handler(EntityNotFound)
    async def _entity_not_found(request: Request, exc: EntityNotFound):
        return _response(request, 404, "not_found", str(exc), {"entity_type": exc.entity_type.value, "entity_id": str(exc.entity_id)})

    @app.exception_handler(GraphTooLarge)
    async def _graph_too_large(request: Request, exc: GraphTooLarge):
        return _response(request, 400, "graph_too_large", str(exc), {"max_nodes": exc.max_nodes, "depth": exc.depth})

    @app.exception_handler(UnknownGraphType)
    async def _graph_type(request: Request, exc: UnknownGraphType):
        from app.repositories.graph import GRAPH_TYPES
        return _response(request, 404, "not_found", str(exc), {"known": sorted(GRAPH_TYPES)})

    @app.exception_handler(ImmutableModel)
    async def _immutable(request: Request, exc: ImmutableModel):
        return _response(request, 405, "immutable", str(exc))

    @app.exception_handler(HardDeleteNotAllowed)
    async def _hard_delete(request: Request, exc: HardDeleteNotAllowed):
        return _response(request, 405, "hard_delete_not_allowed", str(exc))

    @app.exception_handler(RepositoryError)
    async def _repo(request: Request, exc: RepositoryError):
        return _response(request, 400, "invalid_operation", str(exc))

    @app.exception_handler(TenantContextMissing)
    async def _no_tenant(request: Request, exc: TenantContextMissing):
        return _response(request, 401, "unauthorized", "Authentication required")

    @app.exception_handler(TokenError)
    async def _token(request: Request, exc: TokenError):
        return _response(request, 401, "unauthorized", str(exc))

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        errors = [{"loc": [str(x) for x in e.get("loc", [])], "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
        return _response(request, 422, "validation_error", "Request validation failed", {"errors": errors})

    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError):
        detail = str(getattr(exc.orig, "args", [""])[0]).splitlines()[0] if exc.orig else str(exc)
        return _response(request, 409, "conflict", "The change violates a database constraint", {"constraint": detail})

    @app.exception_handler(DBAPIError)
    async def _dbapi(request: Request, exc: DBAPIError):
        sqlstate = getattr(exc.orig, "sqlstate", None) or getattr(exc.orig, "pgcode", None)
        if sqlstate == "42501":  # insufficient_privilege: an RLS WITH CHECK or a revoked table
            return _response(request, 403, "permission_denied", "The database refused this operation for your tenant or role")
        rid = getattr(request.state, "request_id", None)
        log.exception("database error request_id=%s sqlstate=%s", rid, sqlstate)
        return _response(request, 500, "internal_error", "Database error", {"request_id": rid})

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        code = {401: "unauthorized", 403: "permission_denied", 404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return _response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        rid = getattr(request.state, "request_id", None)
        log.exception("unhandled error request_id=%s", rid)
        return _response(request, 500, "internal_error", "Internal server error", {"request_id": rid})
