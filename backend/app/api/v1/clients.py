"""/clients -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /clients/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Client
from app.models.enums import EntityType
from app.repositories import ClientRepository
from app.schemas.clients import ClientCreate, ClientList, ClientRead, ClientUpdate

router = APIRouter(prefix="/clients", tags=["clients"])

SPEC = ResourceSpec(
    name="clients",
    model=Client,
    repo=ClientRepository,
    create=ClientCreate,
    update=ClientUpdate,
    read=ClientRead,
    list=ClientList,
    graph_type="client",
    entity_type=EntityType.CLIENT,
    filters=('slug', 'status'),
    permission_prefix="clients",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
