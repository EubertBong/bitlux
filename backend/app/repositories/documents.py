"""Documents and their polymorphic attachments."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Optional

from app.models import Document, DocumentLink
from app.models.enums import EntityType

from .base import BaseRepository
from .polymorphic import ensure_entity_exists

__all__ = ["DocumentRepository", "DocumentLinkRepository"]


class DocumentLinkRepository(BaseRepository[DocumentLink]):
    model = DocumentLink


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def for_entity(self, entity_type: EntityType, entity_id: uuid.UUID) -> list[Document]:
        """Every live document attached to one entity, via document_links."""
        stmt = (
            self._base_query()
            .join(DocumentLink, DocumentLink.document_id == Document.id)
            .where(
                DocumentLink.entity_type == entity_type,
                DocumentLink.entity_id == entity_id,
                DocumentLink.deleted_at.is_(None),
            )
            .order_by(DocumentLink.is_primary.desc(), Document.document_type, Document.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().unique().all())

    async def expiring_within(self, days: int) -> list[Document]:
        """Insurance certificates, AOCs, passports... anything with an expires_at (DATA_MODEL 5)."""
        today = date.today()
        return await self.list(
            Document.expires_at.between(today, today + timedelta(days=days)),
            order_by=(Document.expires_at,),
            page_size=500,
        )

    async def attach(
        self,
        document_id: uuid.UUID,
        entity_type: EntityType,
        entity_id: uuid.UUID,
        link_role: str = "attachment",
        is_primary: bool = False,
    ) -> DocumentLink:
        """Link a document to an entity. Validates the target in Python first so a
        bad id is an EntityNotFound here, not a trigger error from migration 013."""
        await self.get_or_raise(document_id)
        await ensure_entity_exists(self.session, entity_type, entity_id)
        return await DocumentLinkRepository(self.session).create(
            {"document_id": document_id, "entity_type": entity_type, "entity_id": entity_id,
             "link_role": link_role, "is_primary": is_primary}
        )
