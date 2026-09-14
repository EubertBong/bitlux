"""/segments -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /segments/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Segment
from app.models.enums import EntityType
from app.repositories import SegmentRepository
from app.schemas.segments import SegmentCreate, SegmentList, SegmentRead, SegmentUpdate

router = APIRouter(prefix="/segments", tags=["segments"])

SPEC = ResourceSpec(
    name="segments",
    model=Segment,
    repo=SegmentRepository,
    create=SegmentCreate,
    update=SegmentUpdate,
    read=SegmentRead,
    list=SegmentList,
    graph_type="segment",
    entity_type=EntityType.SEGMENT,
    filters=('parent_segment_id', 'segment_type', 'code'),
    permission_prefix="segments",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
