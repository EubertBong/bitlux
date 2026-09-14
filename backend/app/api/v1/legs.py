"""/legs -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /legs/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends

from app.api.v1._crud import create_child, list_children
from app.deps import RequestContext, require_permission
from app.models import LegCrew, LegPassenger
from app.repositories import LegCrewRepository, LegPassengerRepository
from app.schemas.legs import (LegCrewCreate, LegCrewList, LegCrewRead, LegCrewUpdate, LegPassengerCreate, LegPassengerList,
                              LegPassengerRead, LegPassengerUpdate)

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Leg
from app.models.enums import EntityType
from app.repositories import LegRepository
from app.schemas.legs import LegCreate, LegList, LegRead, LegUpdate

router = APIRouter(prefix="/legs", tags=["legs"])

SPEC = ResourceSpec(
    name="legs",
    model=Leg,
    repo=LegRepository,
    create=LegCreate,
    update=LegUpdate,
    read=LegRead,
    list=LegList,
    graph_type="leg",
    entity_type=EntityType.LEG,
    filters=('trip_id', 'aircraft_id', 'operator_id', 'status', 'departure_airport_id', 'arrival_airport_id'),
    permission_prefix="legs",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


MANIFEST_SPEC = ResourceSpec(name="leg_passengers", model=LegPassenger, repo=LegPassengerRepository, create=LegPassengerCreate,
                             update=LegPassengerUpdate, read=LegPassengerRead, list=LegPassengerList, graph_type="leg",
                             entity_type=EntityType.LEG_PASSENGER, permission_prefix="legs")
CREW_SPEC = ResourceSpec(name="leg_crew", model=LegCrew, repo=LegCrewRepository, create=LegCrewCreate, update=LegCrewUpdate,
                         read=LegCrewRead, list=LegCrewList, graph_type="leg", entity_type=EntityType.LEG_CREW, permission_prefix="legs")


@router.get("/{item_id}/manifest", response_model=list[LegPassengerRead])
async def manifest(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("legs.view"))):
    await LegRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, MANIFEST_SPEC, leg_id=item_id)


@router.post("/{item_id}/manifest", response_model=LegPassengerRead, status_code=201)
async def add_to_manifest(item_id: uuid.UUID, payload: LegPassengerCreate, ctx: RequestContext = Depends(require_permission("legs.edit"))):
    await LegRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, MANIFEST_SPEC, payload, leg_id=item_id)


@router.get("/{item_id}/crew", response_model=list[LegCrewRead])
async def crew(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("legs.view"))):
    await LegRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, CREW_SPEC, leg_id=item_id)


@router.post("/{item_id}/crew", response_model=LegCrewRead, status_code=201)
async def assign_crew(item_id: uuid.UUID, payload: LegCrewCreate, ctx: RequestContext = Depends(require_permission("legs.edit"))):
    await LegRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, CREW_SPEC, payload, leg_id=item_id)



install_crud(router, SPEC)
