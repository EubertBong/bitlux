"""/tasks -- standard CRUD plus resource-specific routes.

Resource-specific routes are registered BEFORE install_crud() so that a literal
path like /tasks/upcoming is matched before the /{item_id} pattern.
"""


import uuid

from fastapi import APIRouter, Depends

from app.deps import RequestContext, require_permission

from app.api.v1._crud import ResourceSpec, install_crud
from app.models import Task
from app.models.enums import EntityType
from app.repositories import TaskRepository
from app.schemas.tasks import TaskCreate, TaskList, TaskRead, TaskUpdate

router = APIRouter(prefix="/tasks", tags=["tasks"])

SPEC = ResourceSpec(
    name="tasks",
    model=Task,
    repo=TaskRepository,
    create=TaskCreate,
    update=TaskUpdate,
    read=TaskRead,
    list=TaskList,
    graph_type="task",
    entity_type=EntityType.TASK,
    filters=('status', 'priority', 'assigned_to_user_id', 'task_type', 'entity_type', 'entity_id'),
    permission_prefix="tasks",
    create_permission=None,
    encrypted_inputs=(),
)

# --- resource-specific routes (before install_crud) ---------------------------


@router.get("/my-queue", response_model=list[TaskRead], summary="Actionable tasks for the caller, most urgent first")
async def my_queue(ctx: RequestContext = Depends(require_permission("tasks.view"))):
    return [TaskRead.model_validate(t) for t in await TaskRepository(ctx.session).my_queue(ctx.user.id)]


@router.get("/overdue", response_model=list[TaskRead])
async def overdue(ctx: RequestContext = Depends(require_permission("tasks.view"))):
    return [TaskRead.model_validate(t) for t in await TaskRepository(ctx.session).overdue()]


@router.post("/{item_id}/complete", response_model=TaskRead)
async def complete(item_id: uuid.UUID, ctx: RequestContext = Depends(require_permission("tasks.edit"))):
    return TaskRead.model_validate(await TaskRepository(ctx.session).complete(item_id))



install_crud(router, SPEC)
