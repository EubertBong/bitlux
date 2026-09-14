"""/crew -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /crew/upcoming is matched before the /{item_id} pattern.
"""


from fastapi import APIRouter, Depends, Query

from app.deps import RequestContext, require_permission

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import CrewMember
from app.models.enums import EntityType
from app.repositories import CrewMemberRepository
from app.schemas.crew import CrewMemberCreate, CrewMemberList, CrewMemberRead, CrewMemberUpdate

router = APIRouter(prefix="/crew", tags=["crew"])

SPEC = ResourceSpec(
    name="crew",
    model=CrewMember,
    repo=CrewMemberRepository,
    create=CrewMemberCreate,
    update=CrewMemberUpdate,
    read=CrewMemberRead,
    list=CrewMemberList,
    graph_type="crew_member",
    entity_type=EntityType.CREW_MEMBER,
    filters=('operator_id', 'status', 'primary_role'),
    permission_prefix="crew",
    create_permission=None,
    encrypted_inputs=('license_number',),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/with-rating/{icao_type_code}", response_model=list[CrewMemberRead], summary="Active crew current on a type")
async def with_rating(icao_type_code: str, ctx: RequestContext = Depends(require_permission("crew.view"))):
    return [CrewMemberRead.model_validate(c) for c in await CrewMemberRepository(ctx.session).with_type_rating(icao_type_code)]


@router.get("/medical-expiring", response_model=list[CrewMemberRead])
async def medical_expiring(days: int = Query(90, ge=1, le=3650), ctx: RequestContext = Depends(require_permission("crew.view"))):
    return [CrewMemberRead.model_validate(c) for c in await CrewMemberRepository(ctx.session).medical_expiring_within(days)]



install_crud(router, SPEC)
