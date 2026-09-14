"""/search -- grouped full-text search across entity types, on the GIN indexes."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.deps import RequestContext, get_context
from app.repositories import SEARCH_TYPES, SearchRepository
from app.schemas.common import SearchHitOut, SearchResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.get("", response_model=SearchResponse, summary="Search everything the caller may view")
async def search(
    q: str = Query(min_length=1, max_length=200),
    types: Optional[str] = Query(None, description=f"Comma-separated subset of: {', '.join(SEARCH_TYPES)}"),
    limit: int = Query(get_settings().search_default_limit, ge=1, le=get_settings().search_max_limit, description="Per type"),
    ctx: RequestContext = Depends(get_context),
) -> SearchResponse:
    wanted = [t.strip() for t in types.split(",")] if types else list(SEARCH_TYPES)
    # Results are filtered by the per-type view permission, not just by RLS.
    allowed = [t for t in wanted if t in SEARCH_TYPES and ctx.can(SEARCH_TYPES[t].permission)]
    grouped = await SearchRepository(ctx.session).search(q, allowed, limit)
    return SearchResponse(query=q, results={k: [SearchHitOut(id=str(h.id), type=h.type, label=h.label, subtitle=h.subtitle, url=h.url, rank=h.rank) for h in v] for k, v in grouped.items()})
