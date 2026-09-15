"""/contacts -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /contacts/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends, Query

from app.api.v1._crud import create_child, list_children
from app.deps import RequestContext, require_permission
from app.models import ContactChannel
from app.repositories import ActivityRepository, ContactChannelRepository, PassengerRepository
from app.schemas.activities import ActivityRead
from app.schemas.contacts import ContactChannelCreate, ContactChannelList, ContactChannelRead, ContactChannelUpdate
from app.schemas.passengers import PassengerRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Contact
from app.models.enums import EntityType
from app.repositories import ContactRepository
from app.schemas.contacts import ContactCreate, ContactList, ContactRead, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])

SPEC = ResourceSpec(
    name="contacts",
    model=Contact,
    repo=ContactRepository,
    create=ContactCreate,
    update=ContactUpdate,
    read=ContactRead,
    list=ContactList,
    graph_type="contact",
    entity_type=EntityType.CONTACT,
    filters=('segment_id', 'status', 'owner_user_id', 'contact_type', 'parent_contact_id', 'source'),
    permission_prefix="contacts",
    create_permission=None,
    encrypted_inputs=(),
    search_type="contacts",
)

# --- resource-specific routes (before install_crud) ---------------------------


CHANNEL_SPEC = ResourceSpec(
    name="contact_channels", model=ContactChannel, repo=ContactChannelRepository,
    create=ContactChannelCreate, update=ContactChannelUpdate, read=ContactChannelRead, list=ContactChannelList,
    graph_type="contact_channel", entity_type=None, permission_prefix="contacts",
)


@router.get("/{item_id}/channels", response_model=list[ContactChannelRead])
async def channels(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("contacts.view"))):
    await ContactRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, CHANNEL_SPEC, contact_id=item_id)


@router.post("/{item_id}/channels", response_model=ContactChannelRead, status_code=201)
async def add_channel(item_id: uuid.UUID, payload: ContactChannelCreate, ctx: RequestContext = Depends(require_permission("contacts.edit"))):
    await ContactRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, CHANNEL_SPEC, payload, contact_id=item_id)


@router.get("/{item_id}/passengers", response_model=list[PassengerRead])
async def passengers(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("passengers.view"))):
    await ContactRepository(ctx.session).get_or_raise(item_id)
    return [PassengerRead.model_validate(p) for p in await PassengerRepository(ctx.session).for_contact(item_id)]


@router.get("/{item_id}/activities", response_model=list[ActivityRead])
async def activities(item_id: uuid.UUID, limit: int = Query(50, ge=1, le=500), ctx: RequestContext = Depends(require_permission("activities.view"))):
    await ContactRepository(ctx.session).get_or_raise(item_id)
    return [ActivityRead.model_validate(a) for a in await ActivityRepository(ctx.session).for_contact(item_id, limit)]



install_crud(router, SPEC)
