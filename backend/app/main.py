"""FastAPI application factory.

    uvicorn app.main:app --reload            (from backend/)

Runtime connects as bitlux_app (APP_DATABASE_URL); every protected request runs
inside a tenant transaction with RLS live. See DATA_MODEL.md 1.7.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.deps import dispose_engine, engine
from app.errors import install_exception_handlers
from app.logging_middleware import RequestLogMiddleware, configure_logging


log = logging.getLogger("app.startup")

_ROLE_SQL = text(
    "SELECT current_user::text, current_setting('is_superuser') = 'on', "
    "(SELECT rolbypassrls FROM pg_roles WHERE rolname = current_user)"
)


async def assert_rls_enforced() -> None:
    """Refuse to serve as a role that bypasses row-level security.

    Superusers, and any role with BYPASSRLS (Neon's console-created roles are
    members of neon_superuser, which has it), are not bound by the tenant
    policies -- even with FORCE ROW LEVEL SECURITY. Running the API as one would
    silently disable tenant isolation, so it is a startup error, in every env.
    An unreachable database is not: /health reports that and the platform
    restarts us when it is back.
    """
    try:
        async with engine().connect() as conn:
            user, superuser, bypass = (await conn.execute(_ROLE_SQL)).one()
    except Exception as exc:  # noqa: BLE001 -- connectivity, not policy
        log.error("database not reachable at startup (%s: %s); /health will report 503 until it is", type(exc).__name__, exc)
        return
    if superuser or bypass:
        raise RuntimeError(
            f"refusing to start: database role {user!r} bypasses row-level security "
            f"(superuser={superuser}, bypassrls={bypass}). APP_DATABASE_URL must connect as the "
            "bitlux_app role, not the schema owner. See DATA_MODEL.md 1.7 and docs/DEPLOY.md."
        )
    log.info("database role %r: RLS enforced", user)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.assert_production_safe()
    engine()  # fail fast on a malformed APP_DATABASE_URL
    await assert_rls_enforced()
    yield
    await dispose_engine()


async def _db_probe() -> None:
    async with engine().connect() as conn:
        await conn.execute(text("SELECT 1"))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title=settings.api_title, version="0.1.0", lifespan=lifespan,
        openapi_url=f"{settings.api_prefix}/openapi.json", docs_url=f"{settings.api_prefix}/docs", redoc_url=None,
    )
    app.state.settings = settings
    app.add_middleware(RequestLogMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=True,
                       allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    install_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["ops"], include_in_schema=False)
    async def health() -> JSONResponse:
        """Platform health check (Render). No auth, no tenant context: one SELECT 1
        through the pool, 200 when it answers, 503 when it does not."""
        try:
            await asyncio.wait_for(_db_probe(), timeout=3.0)
        except Exception as exc:  # noqa: BLE001 -- any failure means "not healthy"
            log.warning("health: database probe failed: %s: %s", type(exc).__name__, exc)
            return JSONResponse({"status": "degraded", "db": "unreachable"}, status_code=503)
        return JSONResponse({"status": "ok", "db": "ok"})

    @app.get("/healthz", tags=["ops"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        """Liveness only (no database round-trip); /health is the readiness check."""
        return {"status": "ok", "env": settings.env}

    return app


app = create_app()
