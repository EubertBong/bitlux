"""/activities -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /activities/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Activity
from app.models.enums import EntityType
from app.repositories import ActivityRepository
from app.schemas.activities import ActivityCreate, ActivityList, ActivityRead, ActivityUpdate

router = APIRouter(prefix="/activities", tags=["activities"])

SPEC = ResourceSpec(
    name="activities",
    model=Activity,
    repo=ActivityRepository,
    create=ActivityCreate,
    update=ActivityUpdate,
    read=ActivityRead,
    list=ActivityList,
    graph_type="activity",
    entity_type=EntityType.ACTIVITY,
    filters=('contact_id', 'activity_type', 'user_id', 'entity_type', 'entity_id', 'direction'),
    permission_prefix="activities",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
