"""/passengers -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /passengers/upcoming is matched before the /{item_id} pattern.
"""


import uuid
from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from app.api.v1._crud import create_child, list_children
from app.deps import RequestContext, require_permission
from app.models import TravelDocument
from app.repositories import TravelDocumentRepository
from app.schemas.legs import LegRead
from app.schemas.passengers import TravelDocumentCreate, TravelDocumentList, TravelDocumentRead, TravelDocumentUpdate

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Passenger
from app.models.enums import EntityType
from app.repositories import PassengerRepository
from app.schemas.passengers import PassengerCreate, PassengerList, PassengerRead, PassengerUpdate

router = APIRouter(prefix="/passengers", tags=["passengers"])

SPEC = ResourceSpec(
    name="passengers",
    model=Passenger,
    repo=PassengerRepository,
    create=PassengerCreate,
    update=PassengerUpdate,
    read=PassengerRead,
    list=PassengerList,
    graph_type="passenger",
    entity_type=EntityType.PASSENGER,
    filters=('contact_id', 'status', 'nationality_code'),
    permission_prefix="passengers",
    create_permission=None,
    encrypted_inputs=('known_traveler_number', 'redress_number'),
)

# --- resource-specific routes (before install_crud) ---------------------------


TRAVEL_DOCUMENT_SPEC = ResourceSpec(
    name="travel_documents", model=TravelDocument, repo=TravelDocumentRepository,
    create=TravelDocumentCreate, update=TravelDocumentUpdate, read=TravelDocumentRead, list=TravelDocumentList,
    graph_type="travel_document", entity_type=EntityType.TRAVEL_DOCUMENT, permission_prefix="passengers",
    encrypted_inputs=("number",),
)


@router.get("/expiring-passports", response_model=list[TravelDocumentRead], summary="Passports expiring within N days")
async def expiring_passports(days: int = Query(180, ge=1, le=3650), ctx: RequestContext = Depends(require_permission("passengers.view"))):
    return [TravelDocumentRead.model_validate(d) for d in await TravelDocumentRepository(ctx.session).expiring_within(days)]


@router.get("/{item_id}/travel-documents", response_model=list[TravelDocumentRead], summary="Travel documents (numbers as last4 only)")
async def travel_documents(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("passengers.view"))):
    await PassengerRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, TRAVEL_DOCUMENT_SPEC, passenger_id=item_id)


@router.post("/{item_id}/travel-documents", response_model=TravelDocumentRead, status_code=201, summary="Add a travel document (number is encrypted at rest)")
async def add_travel_document(item_id: uuid.UUID, payload: TravelDocumentCreate, ctx: RequestContext = Depends(require_permission("passengers.edit"))):
    await PassengerRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, TRAVEL_DOCUMENT_SPEC, payload, passenger_id=item_id)


@router.get("/{item_id}/flight-history", response_model=list[LegRead], summary="Legs this passenger was manifested on, newest first")
async def flight_history(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("passengers.view"))):
    repo = PassengerRepository(ctx.session)
    await repo.get_or_raise(item_id)
    return [LegRead.model_validate(l) for l in await repo.flight_history(item_id)]



install_crud(router, SPEC)
