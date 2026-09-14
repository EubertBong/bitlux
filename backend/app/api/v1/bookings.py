"""/bookings -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /bookings/upcoming is matched before the /{item_id} pattern.
"""


from fastapi import APIRouter, Depends

from app.deps import RequestContext, require_permission

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Booking
from app.models.enums import EntityType
from app.repositories import BookingRepository
from app.schemas.bookings import BookingCreate, BookingList, BookingRead, BookingUpdate

router = APIRouter(prefix="/bookings", tags=["bookings"])

SPEC = ResourceSpec(
    name="bookings",
    model=Booking,
    repo=BookingRepository,
    create=BookingCreate,
    update=BookingUpdate,
    read=BookingRead,
    list=BookingList,
    graph_type="booking",
    entity_type=EntityType.BOOKING,
    filters=('trip_id', 'status', 'account_holder_id', 'quote_id'),
    permission_prefix="bookings",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/awaiting-deposit", response_model=list[BookingRead])
async def awaiting_deposit(ctx: RequestContext = Depends(require_permission("bookings.view"))):
    return [BookingRead.model_validate(b) for b in await BookingRepository(ctx.session).awaiting_deposit()]



install_crud(router, SPEC)
