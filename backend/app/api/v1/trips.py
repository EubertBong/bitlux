"""/trips -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /trips/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends, Query

from app.deps import RequestContext, require_permission
from app.repositories import BookingRepository, LegRepository, QuoteRepository
from app.schemas.bookings import BookingRead
from app.schemas.legs import LegRead
from app.schemas.quotes import QuoteRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Trip
from app.models.enums import EntityType
from app.repositories import TripRepository
from app.schemas.trips import TripCreate, TripList, TripRead, TripUpdate

router = APIRouter(prefix="/trips", tags=["trips"])

SPEC = ResourceSpec(
    name="trips",
    model=Trip,
    repo=TripRepository,
    create=TripCreate,
    update=TripUpdate,
    read=TripRead,
    list=TripList,
    graph_type="trip",
    entity_type=EntityType.TRIP,
    filters=('status', 'account_holder_id', 'primary_contact_id', 'owner_user_id', 'trip_type', 'trip_number'),
    permission_prefix="trips",
    create_permission=None,
    encrypted_inputs=(),
    search_type="trips",
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/upcoming", response_model=TripList, summary="Confirmed / in-progress trips from today")
async def upcoming(page: int = Query(1, ge=1), page_size: int = Query(50, ge=1, le=500), ctx: RequestContext = Depends(require_permission("trips.view"))):
    items = await TripRepository(ctx.session).upcoming(page=page, page_size=page_size)
    return TripList(items=[TripRead.model_validate(t) for t in items], total=len(items), page=page, page_size=page_size)


@router.get("/thin-margin", response_model=list[TripRead], summary="Priced trips with margin below a threshold (cents)")
async def thin_margin(threshold_cents: int = Query(..., ge=0), ctx: RequestContext = Depends(require_permission("trips.view"))):
    return [TripRead.model_validate(t) for t in await TripRepository(ctx.session).with_margin_below(threshold_cents)]


@router.get("/{item_id}/legs", response_model=list[LegRead])
async def legs(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("trips.view"))):
    await TripRepository(ctx.session).get_or_raise(item_id)
    return [LegRead.model_validate(l) for l in await LegRepository(ctx.session).for_trip(item_id)]


@router.get("/{item_id}/quotes", response_model=list[QuoteRead], summary="Current quote revision(s) for the trip")
async def quotes(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("quotes.view"))):
    await TripRepository(ctx.session).get_or_raise(item_id)
    return [QuoteRead.model_validate(q) for q in await QuoteRepository(ctx.session).current_for_trip(item_id)]


@router.get("/{item_id}/booking", response_model=BookingRead | None, summary="The live booking, if any")
async def booking(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("bookings.view"))):
    await TripRepository(ctx.session).get_or_raise(item_id)
    b = await BookingRepository(ctx.session).live_for_trip(item_id)
    return BookingRead.model_validate(b) if b else None



install_crud(router, SPEC)
