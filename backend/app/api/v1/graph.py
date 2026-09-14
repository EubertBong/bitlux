"""/graph/{entity}/{id} -- the relational neighbourhood for the D3 visualiser."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query

from app.config import get_settings
from app.deps import RequestContext, get_context
from app.repositories import GRAPH_TYPES, GraphResolver
from app.schemas.common import GraphResponse

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/types", summary="Node types the graph understands")
async def graph_types(ctx: RequestContext = Depends(get_context)) -> list[str]:
    return sorted(t for t in GRAPH_TYPES if ctx.can(GRAPH_TYPES[t].permission))


@router.get("/{entity}/{entity_id}", response_model=GraphResponse, summary="Nodes and edges around one entity")
async def graph(
    entity: str,
    entity_id: uuid.UUID,
    depth: int = Query(1, ge=1, le=2, description="1 = direct neighbours; 2 = neighbours of neighbours (capped)"),
    ctx: RequestContext = Depends(get_context),
) -> GraphResponse:
    resolver = GraphResolver(ctx.session, can_view=ctx.can, max_nodes=get_settings().graph_max_nodes)
    return await resolver.neighbourhood(entity, entity_id, depth=depth)
