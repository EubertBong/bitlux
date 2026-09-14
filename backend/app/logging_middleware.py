"""Request id propagation and one structured log line per request.

    method path status duration_ms user_id client_id request_id

user_id / client_id are read from request.state, where the auth dependency
puts them; unauthenticated requests log them as "-".
"""

from __future__ import annotations

import logging
import time
import uuid
from contextvars import ContextVar

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

request_id_var: ContextVar[str] = ContextVar("bitlux_request_id", default="-")
log = logging.getLogger("bitlux.request")


class RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get()
        return True


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.addFilter(RequestIdFilter())
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-5s [%(name)s] rid=%(request_id)s %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    logging.getLogger("uvicorn.access").disabled = True  # replaced by the line below


class RequestLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex
        token = request_id_var.set(rid)
        request.state.request_id = rid
        started = time.perf_counter()
        status_code = 500
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            duration_ms = (time.perf_counter() - started) * 1000
            log.info(
                "%s %s status=%s duration_ms=%.1f user_id=%s client_id=%s",
                request.method, request.url.path, status_code, duration_ms,
                getattr(request.state, "user_id", "-"), getattr(request.state, "client_id", "-"),
            )
            request_id_var.reset(token)
