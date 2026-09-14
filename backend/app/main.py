"""FastAPI application factory.

    uvicorn app.main:app --reload            (from backend/)

Runtime connects as bitlux_app (APP_DATABASE_URL); every protected request runs
inside a tenant transaction with RLS live. See DATA_MODEL.md 1.7.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import Settings, get_settings
from app.deps import dispose_engine, engine
from app.errors import install_exception_handlers
from app.logging_middleware import RequestLogMiddleware, configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    settings.assert_production_safe()
    engine()  # fail fast on a bad DATABASE_URL
    yield
    await dispose_engine()


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

    @app.get("/healthz", tags=["ops"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "env": settings.env}

    return app


app = create_app()
