"""/account_holders -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /account_holders/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends

from app.deps import RequestContext, require_permission
from app.repositories import InvoiceRepository, PassengerRepository
from app.schemas.invoices import InvoiceRead
from app.schemas.passengers import PassengerRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import AccountHolder
from app.models.enums import EntityType
from app.repositories import AccountHolderRepository
from app.schemas.account_holders import AccountHolderCreate, AccountHolderList, AccountHolderRead, AccountHolderUpdate

router = APIRouter(prefix="/account_holders", tags=["account_holders"])

SPEC = ResourceSpec(
    name="account_holders",
    model=AccountHolder,
    repo=AccountHolderRepository,
    create=AccountHolderCreate,
    update=AccountHolderUpdate,
    read=AccountHolderRead,
    list=AccountHolderList,
    graph_type="account_holder",
    entity_type=EntityType.ACCOUNT_HOLDER,
    filters=('status', 'account_type', 'primary_contact_id'),
    permission_prefix="account_holders",
    create_permission=None,
    encrypted_inputs=('tax_id',),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/{item_id}/invoices", response_model=list[InvoiceRead])
async def invoices(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("invoices.view"))):
    await AccountHolderRepository(ctx.session).get_or_raise(item_id)
    return [InvoiceRead.model_validate(i) for i in await InvoiceRepository(ctx.session).for_account_holder(item_id)]



install_crud(router, SPEC)
