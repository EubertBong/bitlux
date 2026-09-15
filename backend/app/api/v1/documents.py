"""/documents -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /documents/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.deps import RequestContext, require_permission
from app.schemas.documents import DocumentLinkRead

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Document
from app.models.enums import EntityType
from app.repositories import DocumentRepository
from app.schemas.documents import DocumentCreate, DocumentList, DocumentRead, DocumentUpdate

router = APIRouter(prefix="/documents", tags=["documents"])

SPEC = ResourceSpec(
    name="documents",
    model=Document,
    repo=DocumentRepository,
    create=DocumentCreate,
    update=DocumentUpdate,
    read=DocumentRead,
    list=DocumentList,
    graph_type="document",
    entity_type=EntityType.DOCUMENT,
    filters=('document_type', 'status'),
    permission_prefix="documents",
    create_permission='documents.upload',
    encrypted_inputs=(),
    search_type="documents",
)

# --- resource-specific routes (before install_crud) ---------------------------


class AttachRequest(BaseModel):
    entity_type: EntityType
    entity_id: uuid.UUID
    link_role: str = "attachment"
    is_primary: bool = False


@router.get("/expiring", response_model=list[DocumentRead], summary="Documents whose expires_at falls within N days")
async def expiring(days: int = Query(90, ge=1, le=3650), ctx: RequestContext = Depends(require_permission("documents.view"))):
    return [DocumentRead.model_validate(d) for d in await DocumentRepository(ctx.session).expiring_within(days)]


@router.get("/for/{entity_type}/{entity_id}", response_model=list[DocumentRead], summary="Documents attached to any entity")
async def for_entity(entity_type: EntityType, entity_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("documents.view"))):
    return [DocumentRead.model_validate(d) for d in await DocumentRepository(ctx.session).for_entity(entity_type, entity_id)]


@router.post("/{item_id}/links", response_model=DocumentLinkRead, status_code=201, summary="Attach a document to an entity (target validated first)")
async def attach(item_id: uuid.UUID, body: AttachRequest, ctx: RequestContext = Depends(require_permission("documents.upload"))):
    link = await DocumentRepository(ctx.session).attach(item_id, body.entity_type, body.entity_id, body.link_role, body.is_primary)
    return DocumentLinkRead.model_validate(link)



install_crud(router, SPEC)
