"""/airports -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /airports/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends, Query

from app.deps import RequestContext, require_permission
from app.repositories import FBORepository
from app.schemas.airports import FBORead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Airport
from app.models.enums import EntityType
from app.repositories import AirportRepository
from app.schemas.airports import AirportCreate, AirportList, AirportRead, AirportUpdate

router = APIRouter(prefix="/airports", tags=["airports"])

SPEC = ResourceSpec(
    name="airports",
    model=Airport,
    repo=AirportRepository,
    create=AirportCreate,
    update=AirportUpdate,
    read=AirportRead,
    list=AirportList,
    graph_type="airport",
    entity_type=EntityType.AIRPORT,
    filters=('country_code', 'icao_code', 'iata_code', 'is_active'),
    permission_prefix="airports",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/nearby", summary="Airports within a radius (nm), nearest first -- haversine, not planar")
async def nearby(lat: float = Query(..., ge=-90, le=90), lon: float = Query(..., ge=-180, le=180), radius_nm: float = Query(50, gt=0, le=1000),
                 ctx: RequestContext = Depends(require_permission("airports.view"))):
    hits = await AirportRepository(ctx.session).nearby(lat, lon, radius_nm)
    return [{"airport": AirportRead.model_validate(a), "distance_nm": round(d, 1)} for a, d in hits]


@router.get("/by-code/{code}", response_model=AirportRead, summary="ICAO or IATA")
async def by_code(code: str, ctx: RequestContext = Depends(require_permission("airports.view"))):
    from app.repositories.base import NotFound
    a = await AirportRepository(ctx.session).by_code(code)
    if a is None:
        raise NotFound(Airport, code)
    return AirportRead.model_validate(a)


@router.get("/{item_id}/fbos", response_model=list[FBORead])
async def fbos(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("airports.view"))):
    await AirportRepository(ctx.session).get_or_raise(item_id)
    return [FBORead.model_validate(f) for f in await FBORepository(ctx.session).at_airport(item_id)]



install_crud(router, SPEC)
