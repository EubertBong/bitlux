"""/aircraft_models -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /aircraft_models/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import AircraftModel
from app.models.enums import EntityType
from app.repositories import AircraftModelRepository
from app.schemas.aircraft_models import AircraftModelCreate, AircraftModelList, AircraftModelRead, AircraftModelUpdate

router = APIRouter(prefix="/aircraft_models", tags=["aircraft_models"])

SPEC = ResourceSpec(
    name="aircraft_models",
    model=AircraftModel,
    repo=AircraftModelRepository,
    create=AircraftModelCreate,
    update=AircraftModelUpdate,
    read=AircraftModelRead,
    list=AircraftModelList,
    graph_type="aircraft_model",
    entity_type=EntityType.AIRCRAFT_MODEL,
    filters=('manufacturer_id', 'category'),
    permission_prefix="aircraft_models",
    create_permission=None,
    encrypted_inputs=(),
    search_type="aircraft_models",
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
