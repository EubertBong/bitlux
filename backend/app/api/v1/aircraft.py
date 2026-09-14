"""/aircraft -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /aircraft/upcoming is matched before the /{item_id} pattern.
"""


import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query

from app.deps import RequestContext, require_permission
from app.schemas.legs import LegRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Aircraft
from app.models.enums import EntityType
from app.repositories import AircraftRepository
from app.schemas.aircraft import AircraftCreate, AircraftList, AircraftRead, AircraftUpdate

router = APIRouter(prefix="/aircraft", tags=["aircraft"])

SPEC = ResourceSpec(
    name="aircraft",
    model=Aircraft,
    repo=AircraftRepository,
    create=AircraftCreate,
    update=AircraftUpdate,
    read=AircraftRead,
    list=AircraftList,
    graph_type="aircraft",
    entity_type=EntityType.AIRCRAFT,
    filters=('operator_id', 'aircraft_model_id', 'status', 'is_available_for_charter', 'home_base_airport_id'),
    permission_prefix="aircraft",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/available", response_model=list[AircraftRead], summary="Tails of a type with no leg overlapping the window")
async def available(aircraft_model_id: uuid.UUID, start: datetime, end: datetime, ctx: RequestContext = Depends(require_permission("aircraft.view"))):
    return [AircraftRead.model_validate(a) for a in await AircraftRepository(ctx.session).available_between(aircraft_model_id, start, end)]


@router.get("/by-tail/{tail_number}", response_model=AircraftRead)
async def by_tail(tail_number: str, ctx: RequestContext = Depends(require_permission("aircraft.view"))):
    from app.repositories.base import NotFound
    a = await AircraftRepository(ctx.session).by_tail(tail_number)
    if a is None:
        raise NotFound(Aircraft, tail_number)
    return AircraftRead.model_validate(a)


@router.get("/{item_id}/conflicts", response_model=list[LegRead], summary="Legs overlapping a proposed window")
async def conflicts(item_id: uuid.UUID, start: datetime, end: datetime, ctx: RequestContext = Depends(require_permission("aircraft.view"))):
    repo = AircraftRepository(ctx.session)
    await repo.get_or_raise(item_id)
    return [LegRead.model_validate(l) for l in await repo.conflicting_legs(item_id, start, end)]


@router.get("/{item_id}/double-booked", response_model=list[LegRead], summary="Conflicting legs at an instant (empty = fine)")
async def double_booked(item_id: uuid.UUID, at: datetime, ctx: RequestContext = Depends(require_permission("aircraft.view"))):
    repo = AircraftRepository(ctx.session)
    await repo.get_or_raise(item_id)
    return [LegRead.model_validate(l) for l in await repo.double_booked(item_id, at)]



install_crud(router, SPEC)
