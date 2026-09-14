"""/manufacturers -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /manufacturers/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Manufacturer
from app.models.enums import EntityType
from app.repositories import ManufacturerRepository
from app.schemas.manufacturers import ManufacturerCreate, ManufacturerList, ManufacturerRead, ManufacturerUpdate

router = APIRouter(prefix="/manufacturers", tags=["manufacturers"])

SPEC = ResourceSpec(
    name="manufacturers",
    model=Manufacturer,
    repo=ManufacturerRepository,
    create=ManufacturerCreate,
    update=ManufacturerUpdate,
    read=ManufacturerRead,
    list=ManufacturerList,
    graph_type="manufacturer",
    entity_type=EntityType.MANUFACTURER,
    filters=('country_code', 'is_active'),
    permission_prefix="manufacturers",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
