"""/payments -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /payments/upcoming is matched before the /{item_id} pattern.
"""

from fastapi import APIRouter

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Payment
from app.models.enums import EntityType
from app.repositories import PaymentRepository
from app.schemas.payments import PaymentCreate, PaymentList, PaymentRead, PaymentUpdate

router = APIRouter(prefix="/payments", tags=["payments"])

SPEC = ResourceSpec(
    name="payments",
    model=Payment,
    repo=PaymentRepository,
    create=PaymentCreate,
    update=PaymentUpdate,
    read=PaymentRead,
    list=PaymentList,
    graph_type="payment",
    entity_type=EntityType.PAYMENT,
    filters=('account_holder_id', 'invoice_id', 'status', 'method'),
    permission_prefix="payments",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


install_crud(router, SPEC)
