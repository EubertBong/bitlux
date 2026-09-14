"""/quotes -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /quotes/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends

from app.api.v1._crud import create_child, list_children, to_repo_payload
from app.deps import RequestContext, require_permission
from app.models import QuoteLineItem
from app.repositories import QuoteLineItemRepository
from app.schemas.quotes import QuoteLineItemCreate, QuoteLineItemList, QuoteLineItemRead, QuoteLineItemUpdate

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Quote
from app.models.enums import EntityType
from app.repositories import QuoteRepository
from app.schemas.quotes import QuoteCreate, QuoteList, QuoteRead, QuoteUpdate

router = APIRouter(prefix="/quotes", tags=["quotes"])

SPEC = ResourceSpec(
    name="quotes",
    model=Quote,
    repo=QuoteRepository,
    create=QuoteCreate,
    update=QuoteUpdate,
    read=QuoteRead,
    list=QuoteList,
    graph_type="quote",
    entity_type=EntityType.QUOTE,
    filters=('trip_id', 'status', 'account_holder_id', 'is_current', 'quote_number'),
    permission_prefix="quotes",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


LINE_SPEC = ResourceSpec(name="quote_line_items", model=QuoteLineItem, repo=QuoteLineItemRepository, create=QuoteLineItemCreate,
                         update=QuoteLineItemUpdate, read=QuoteLineItemRead, list=QuoteLineItemList, graph_type="quote_line_item",
                         entity_type=None, permission_prefix="quotes")


@router.get("/{item_id}/line-items", response_model=list[QuoteLineItemRead])
async def line_items(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("quotes.view"))):
    await QuoteRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, LINE_SPEC, order_by=(QuoteLineItem.sort_order,), quote_id=item_id)


@router.post("/{item_id}/line-items", response_model=QuoteLineItemRead, status_code=201)
async def add_line_item(item_id: uuid.UUID, payload: QuoteLineItemCreate, ctx: RequestContext = Depends(require_permission("quotes.edit"))):
    await QuoteRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, LINE_SPEC, payload, quote_id=item_id)


@router.get("/{item_id}/revisions", response_model=list[QuoteRead], summary="Every revision of this quote number, oldest first")
async def revisions(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("quotes.view"))):
    repo = QuoteRepository(ctx.session)
    q = await repo.get_or_raise(item_id)
    return [QuoteRead.model_validate(r) for r in await repo.revisions(q.quote_number)]


@router.post("/{item_id}/supersede", response_model=QuoteRead, status_code=201, summary="Create revision N+1 (line items copied unless supplied)")
async def supersede(item_id: uuid.UUID, payload: QuoteUpdate, ctx: RequestContext = Depends(require_permission("quotes.edit"))):
    data = to_repo_payload(SPEC, payload.model_dump(exclude_unset=True, by_alias=False))
    new = await QuoteRepository(ctx.session).supersede(item_id, data)
    return QuoteRead.model_validate(new)



install_crud(router, SPEC)
