"""/empty_legs -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /empty_legs/upcoming is matched before the /{item_id} pattern.
"""


from datetime import date

from fastapi import APIRouter, Depends, Query

from app.deps import RequestContext, require_permission
from app.models.enums import AircraftCategory

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import EmptyLeg
from app.models.enums import EntityType
from app.repositories import EmptyLegRepository
from app.schemas.empty_legs import EmptyLegCreate, EmptyLegList, EmptyLegRead, EmptyLegUpdate

router = APIRouter(prefix="/empty_legs", tags=["empty_legs"])

SPEC = ResourceSpec(
    name="empty_legs",
    model=EmptyLeg,
    repo=EmptyLegRepository,
    create=EmptyLegCreate,
    update=EmptyLegUpdate,
    read=EmptyLegRead,
    list=EmptyLegList,
    graph_type="empty_leg",
    entity_type=EntityType.EMPTY_LEG,
    filters=('operator_id', 'status', 'departure_airport_id', 'arrival_airport_id', 'source'),
    permission_prefix="empty_legs",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/search", response_model=list[EmptyLegRead], summary="Available empty legs on a route in a date window")
async def search(origin: str, destination: str, date_from: date, date_to: date, cabin_class: AircraftCategory | None = None,
                 limit: int = Query(50, ge=1, le=200), ctx: RequestContext = Depends(require_permission("empty_legs.view"))):
    rows = await EmptyLegRepository(ctx.session).search(origin, destination, date_from, date_to, cabin_class, limit)
    return [EmptyLegRead.model_validate(r) for r in rows]



install_crud(router, SPEC)
