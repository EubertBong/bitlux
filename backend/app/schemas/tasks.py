"""Schemas for /tasks. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import EntityType, TaskPriority, TaskStatus, TaskType


class TaskBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    title: str
    description: Optional[str] = None
    task_type: TaskType = TaskType.OTHER
    status: TaskStatus = TaskStatus.OPEN
    priority: TaskPriority = TaskPriority.NORMAL
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_team: Optional[str] = None
    entity_type: Optional[EntityType] = None
    entity_id: Optional[uuid.UUID] = None
    parent_task_id: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_user_id: Optional[uuid.UUID] = None
    blocked_reason: Optional[str] = None
    recurrence_rule: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    sla_breached_at: Optional[datetime] = None
    source_system: Optional[str] = None
    dedupe_key: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    title: Optional[str] = None
    description: Optional[str] = None
    task_type: Optional[TaskType] = None
    status: Optional[TaskStatus] = None
    priority: Optional[TaskPriority] = None
    assigned_to_user_id: Optional[uuid.UUID] = None
    assigned_team: Optional[str] = None
    entity_type: Optional[EntityType] = None
    entity_id: Optional[uuid.UUID] = None
    parent_task_id: Optional[uuid.UUID] = None
    due_at: Optional[datetime] = None
    reminder_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    completed_by_user_id: Optional[uuid.UUID] = None
    blocked_reason: Optional[str] = None
    recurrence_rule: Optional[str] = None
    sla_due_at: Optional[datetime] = None
    sla_breached_at: Optional[datetime] = None
    source_system: Optional[str] = None
    dedupe_key: Optional[str] = None


class TaskRead(TaskBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class TaskList(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
