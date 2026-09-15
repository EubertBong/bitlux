"""/operators -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /operators/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends, Query

from app.api.v1._crud import create_child, list_children
from app.deps import RequestContext, require_permission
from app.models import OperatorSafetyRating
from app.repositories import OperatorSafetyRatingRepository
from app.schemas.operators import (OperatorSafetyRatingCreate, OperatorSafetyRatingList, OperatorSafetyRatingRead,
                                   OperatorSafetyRatingUpdate)

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Operator
from app.models.enums import EntityType
from app.repositories import OperatorRepository
from app.schemas.operators import OperatorCreate, OperatorList, OperatorRead, OperatorUpdate

router = APIRouter(prefix="/operators", tags=["operators"])

SPEC = ResourceSpec(
    name="operators",
    model=Operator,
    repo=OperatorRepository,
    create=OperatorCreate,
    update=OperatorUpdate,
    read=OperatorRead,
    list=OperatorList,
    graph_type="operator",
    entity_type=EntityType.OPERATOR,
    filters=('status', 'country_code', 'regulatory_part', 'is_preferred'),
    permission_prefix="operators",
    create_permission=None,
    encrypted_inputs=(),
    search_type="operators",
)

# --- resource-specific routes (before install_crud) ---------------------------


RATING_SPEC = ResourceSpec(name="operator_safety_ratings", model=OperatorSafetyRating, repo=OperatorSafetyRatingRepository,
                           create=OperatorSafetyRatingCreate, update=OperatorSafetyRatingUpdate, read=OperatorSafetyRatingRead,
                           list=OperatorSafetyRatingList, graph_type="operator_safety_rating",
                           entity_type=EntityType.OPERATOR_SAFETY_RATING, permission_prefix="operators")


@router.get("/lapsed-ratings", response_model=list[OperatorRead], summary="Operators whose current rating has expired")
async def lapsed(ctx: RequestContext = Depends(require_permission("operators.view"))):
    return [OperatorRead.model_validate(o) for o in await OperatorRepository(ctx.session).with_lapsed_rating()]


@router.get("/insurance-expiring", response_model=list[OperatorRead])
async def insurance_expiring(days: int = Query(90, ge=1, le=3650), ctx: RequestContext = Depends(require_permission("operators.view"))):
    return [OperatorRead.model_validate(o) for o in await OperatorRepository(ctx.session).insurance_expiring_within(days)]


@router.get("/{item_id}/safety-ratings", response_model=list[OperatorSafetyRatingRead])
async def safety_ratings(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("operators.view"))):
    await OperatorRepository(ctx.session).get_or_raise(item_id)
    return await list_children(ctx, RATING_SPEC, operator_id=item_id)


@router.post("/{item_id}/safety-ratings", response_model=OperatorSafetyRatingRead, status_code=201)
async def add_safety_rating(item_id: uuid.UUID, payload: OperatorSafetyRatingCreate, ctx: RequestContext = Depends(require_permission("operators.edit"))):
    await OperatorRepository(ctx.session).get_or_raise(item_id)
    return await create_child(ctx, RATING_SPEC, payload, operator_id=item_id)



install_crud(router, SPEC)
