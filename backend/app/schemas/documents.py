"""Schemas for /documents. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import DocumentStatus, DocumentType, EntityType, StorageProvider


class DocumentBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    document_type: DocumentType
    status: DocumentStatus = DocumentStatus.PENDING
    title: str
    description: Optional[str] = None
    storage_provider: StorageProvider = StorageProvider.S3
    bucket: str
    storage_key: str
    filename: str
    mime_type: str
    byte_size: int
    checksum_sha256: str
    version: int = 1
    supersedes_document_id: Optional[uuid.UUID] = None
    is_confidential: bool = False
    effective_date: Optional[date] = None
    expires_at: Optional[date] = None
    retention_until: Optional[date] = None
    uploaded_by_user_id: Optional[uuid.UUID] = None
    ocr_text: Optional[str] = None
    metadata_: dict[str, Any] = Field(default_factory=dict, alias="metadata", serialization_alias="metadata")


class DocumentCreate(DocumentBase):
    pass


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_type: Optional[DocumentType] = None
    status: Optional[DocumentStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    storage_provider: Optional[StorageProvider] = None
    bucket: Optional[str] = None
    storage_key: Optional[str] = None
    filename: Optional[str] = None
    mime_type: Optional[str] = None
    byte_size: Optional[int] = None
    checksum_sha256: Optional[str] = None
    version: Optional[int] = None
    supersedes_document_id: Optional[uuid.UUID] = None
    is_confidential: Optional[bool] = None
    effective_date: Optional[date] = None
    expires_at: Optional[date] = None
    retention_until: Optional[date] = None
    uploaded_by_user_id: Optional[uuid.UUID] = None
    ocr_text: Optional[str] = None
    metadata_: Optional[dict[str, Any]] = Field(default=None, alias="metadata", serialization_alias="metadata")


class DocumentRead(DocumentBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class DocumentList(BaseModel):
    items: list[DocumentRead]
    total: int
    page: int
    page_size: int


class DocumentLinkBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    document_id: uuid.UUID
    entity_type: EntityType
    entity_id: uuid.UUID
    link_role: str = 'attachment'
    is_primary: bool = False


class DocumentLinkCreate(DocumentLinkBase):
    pass


class DocumentLinkUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    document_id: Optional[uuid.UUID] = None
    entity_type: Optional[EntityType] = None
    entity_id: Optional[uuid.UUID] = None
    link_role: Optional[str] = None
    is_primary: Optional[bool] = None


class DocumentLinkRead(DocumentLinkBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class DocumentLinkList(BaseModel):
    items: list[DocumentLinkRead]
    total: int
    page: int
    page_size: int
