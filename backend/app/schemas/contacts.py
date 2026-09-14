"""Schemas for /contacts. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import ChannelType, ContactStatus, ContactType, LeadSource


class ContactBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    segment_id: Optional[uuid.UUID] = None
    contact_type: ContactType = ContactType.INDIVIDUAL
    status: ContactStatus = ContactStatus.LEAD
    salutation: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    display_name: str
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    parent_contact_id: Optional[uuid.UUID] = None
    referred_by_contact_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    source: LeadSource = LeadSource.OTHER
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    preferred_language: Optional[str] = None
    lifetime_value_cents: int = 0
    trip_count: int = 0
    last_activity_at: Optional[datetime] = None
    do_not_contact: bool = False
    vip_notes: Optional[str] = None
    preferences: dict[str, Any] = Field(default_factory=dict)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    segment_id: Optional[uuid.UUID] = None
    contact_type: Optional[ContactType] = None
    status: Optional[ContactStatus] = None
    salutation: Optional[str] = None
    first_name: Optional[str] = None
    middle_name: Optional[str] = None
    last_name: Optional[str] = None
    suffix: Optional[str] = None
    display_name: Optional[str] = None
    company_name: Optional[str] = None
    job_title: Optional[str] = None
    parent_contact_id: Optional[uuid.UUID] = None
    referred_by_contact_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    source: Optional[LeadSource] = None
    primary_email: Optional[str] = None
    primary_phone: Optional[str] = None
    preferred_language: Optional[str] = None
    lifetime_value_cents: Optional[int] = None
    trip_count: Optional[int] = None
    last_activity_at: Optional[datetime] = None
    do_not_contact: Optional[bool] = None
    vip_notes: Optional[str] = None
    preferences: Optional[dict[str, Any]] = None


class ContactRead(ContactBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class ContactList(BaseModel):
    items: list[ContactRead]
    total: int
    page: int
    page_size: int


class ContactChannelBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    contact_id: uuid.UUID
    channel_type: ChannelType
    value: str
    label: Optional[str] = None
    is_primary: bool = False
    verified_at: Optional[datetime] = None
    opted_out_at: Optional[datetime] = None


class ContactChannelCreate(ContactChannelBase):
    pass


class ContactChannelUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    contact_id: Optional[uuid.UUID] = None
    channel_type: Optional[ChannelType] = None
    value: Optional[str] = None
    label: Optional[str] = None
    is_primary: Optional[bool] = None
    verified_at: Optional[datetime] = None
    opted_out_at: Optional[datetime] = None


class ContactChannelRead(ContactChannelBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class ContactChannelList(BaseModel):
    items: list[ContactChannelRead]
    total: int
    page: int
    page_size: int
