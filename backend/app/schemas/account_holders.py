"""Schemas for /account_holders. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import AccountStatus, AccountType, PaxRelationship, PaymentTerms


class AccountHolderBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    account_number: str
    name: str
    account_type: AccountType = AccountType.INDIVIDUAL
    status: AccountStatus = AccountStatus.PENDING
    primary_contact_id: uuid.UUID
    billing_contact_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    currency: str = 'USD'
    payment_terms: PaymentTerms = PaymentTerms.PREPAID
    credit_limit_cents: int = 0
    balance_cents: int = 0
    prepaid_balance_cents: int = 0
    tax_exempt: bool = False
    billing_address_id: Optional[uuid.UUID] = None
    contract_signed_at: Optional[datetime] = None
    credit_reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None


class AccountHolderCreate(AccountHolderBase):
    tax_id: Optional[str] = Field(default=None, description="Plaintext; stored encrypted, returned only as *_last4.")


class AccountHolderUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    account_number: Optional[str] = None
    name: Optional[str] = None
    account_type: Optional[AccountType] = None
    status: Optional[AccountStatus] = None
    primary_contact_id: Optional[uuid.UUID] = None
    billing_contact_id: Optional[uuid.UUID] = None
    owner_user_id: Optional[uuid.UUID] = None
    currency: Optional[str] = None
    payment_terms: Optional[PaymentTerms] = None
    credit_limit_cents: Optional[int] = None
    balance_cents: Optional[int] = None
    prepaid_balance_cents: Optional[int] = None
    tax_exempt: Optional[bool] = None
    billing_address_id: Optional[uuid.UUID] = None
    contract_signed_at: Optional[datetime] = None
    credit_reviewed_at: Optional[datetime] = None
    notes: Optional[str] = None
    tax_id: Optional[str] = None


class AccountHolderRead(AccountHolderBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    tax_id_last4: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AccountHolderList(BaseModel):
    items: list[AccountHolderRead]
    total: int
    page: int
    page_size: int


class AccountHolderPassengerBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    account_holder_id: uuid.UUID
    passenger_id: uuid.UUID
    relationship: PaxRelationship = PaxRelationship.OTHER
    is_authorized_booker: bool = False
    spend_limit_cents: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class AccountHolderPassengerCreate(AccountHolderPassengerBase):
    pass


class AccountHolderPassengerUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    account_holder_id: Optional[uuid.UUID] = None
    passenger_id: Optional[uuid.UUID] = None
    relationship: Optional[PaxRelationship] = None
    is_authorized_booker: Optional[bool] = None
    spend_limit_cents: Optional[int] = None
    valid_from: Optional[date] = None
    valid_to: Optional[date] = None


class AccountHolderPassengerRead(AccountHolderPassengerBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class AccountHolderPassengerList(BaseModel):
    items: list[AccountHolderPassengerRead]
    total: int
    page: int
    page_size: int
