"""/invoices -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /invoices/upcoming is matched before the /{item_id} pattern.
"""


import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.api.v1._crud import create_child, list_children
from app.deps import RequestContext, require_permission
from app.models import InvoiceLineItem
from app.repositories import InvoiceLineItemRepository, PaymentRepository
from app.schemas.invoices import InvoiceLineItemCreate, InvoiceLineItemList, InvoiceLineItemRead, InvoiceLineItemUpdate
from app.schemas.payments import PaymentRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Invoice
from app.models.enums import EntityType
from app.repositories import InvoiceRepository
from app.schemas.invoices import InvoiceCreate, InvoiceList, InvoiceRead, InvoiceUpdate

router = APIRouter(prefix="/invoices", tags=["invoices"])

SPEC = ResourceSpec(
    name="invoices",
    model=Invoice,
    repo=InvoiceRepository,
    create=InvoiceCreate,
    update=InvoiceUpdate,
    read=InvoiceRead,
    list=InvoiceList,
    graph_type="invoice",
    entity_type=EntityType.INVOICE,
    filters=('status', 'account_holder_id', 'booking_id', 'trip_id', 'invoice_type'),
    permission_prefix="invoices",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


LINE_SPEC = ResourceSpec(name="invoice_line_items", model=InvoiceLineItem, repo=InvoiceLineItemRepository, create=InvoiceLineItemCreate,
                         update=InvoiceLineItemUpdate, read=InvoiceLineItemRead, list=InvoiceLineItemList, graph_type="invoice_line_item",
                         entity_type=None, permission_prefix="invoices")


@router.get("/ar-aging", summary="Outstanding balance by days past due")
async def ar_aging(as_of: date | None = None, ctx: RequestContext = Depends(require_permission("invoices.view"))):
    report = await InvoiceRepository(ctx.session).ar_aging(as_of)
    return {"as_of": report.as_of.isoformat(), "total_cents": report.total_cents, "overdue_cents": report.overdue_cents,
            "buckets": {k: {"count": b.count, "balance_cents": b.balance_cents} for k, b in report.buckets.items()}}


@router.get("/overdue", response_model=list[InvoiceRead])
async def overdue(ctx: RequestContext = Depends(require_permission("invoices.view"))):
    return [InvoiceRead.model_validate(i) for i in await InvoiceRepository(ctx.session).overdue()]


@router.get("/{item_id}/line-items", response_model=list[InvoiceLineItemRead])
async def line_items(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("invoices.view"))):
    await InvoiceRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, LINE_SPEC, order_by=(InvoiceLineItem.sort_order,), invoice_id=item_id)


@router.post("/{item_id}/line-items", response_model=InvoiceLineItemRead, status_code=201)
async def add_line_item(item_id: uuid.UUID, payload: InvoiceLineItemCreate, ctx: RequestContext = Depends(require_permission("invoices.edit"))):
    await InvoiceRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, LINE_SPEC, payload, invoice_id=item_id)


@router.get("/{item_id}/payments", response_model=list[PaymentRead])
async def payments(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("payments.view"))):
    await InvoiceRepository(ctx.session).get_or_raise(item_id)
    return [PaymentRead.model_validate(p) for p in await PaymentRepository(ctx.session).for_invoice(item_id)]



install_crud(router, SPEC)
