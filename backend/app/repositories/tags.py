"""Tags and polymorphic tagging."""

from __future__ import annotations

import uuid

from app.models import EntityTag, Tag
from app.models.enums import EntityType

from .base import BaseRepository
from .polymorphic import ensure_entity_exists

__all__ = ["TagRepository", "EntityTagRepository"]


class EntityTagRepository(BaseRepository[EntityTag]):
    model = EntityTag


class TagRepository(BaseRepository[Tag]):
    model = Tag

    async def by_name(self, name: str):
        return (await self.session.execute(self._base_query().where(Tag.name == name))).scalar_one_or_none()

    async def for_entity(self, entity_type: EntityType, entity_id: uuid.UUID) -> list[Tag]:
        stmt = (
            self._base_query()
            .join(EntityTag, EntityTag.tag_id == Tag.id)
            .where(EntityTag.entity_type == entity_type, EntityTag.entity_id == entity_id, EntityTag.deleted_at.is_(None))
            .order_by(Tag.name)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def apply(self, tag_id: uuid.UUID, entity_type: EntityType, entity_id: uuid.UUID) -> EntityTag:
        await self.get_or_raise(tag_id)
        await ensure_entity_exists(self.session, entity_type, entity_id)
        return await EntityTagRepository(self.session).create({"tag_id": tag_id, "entity_type": entity_type, "entity_id": entity_id})
