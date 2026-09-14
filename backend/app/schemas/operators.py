"""Schemas for /operators. Generated from app.models; regenerate rather than hand-edit field lists."""

import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import OperatorStatus, PaymentTerms, RegulatoryPart, SafetyProgram, SafetyRatingLevel


class OperatorBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    legal_name: str
    dba_name: Optional[str] = None
    operator_code: Optional[str] = None
    status: OperatorStatus = OperatorStatus.PROSPECT
    country_code: Optional[str] = None
    regulatory_part: Optional[RegulatoryPart] = None
    aoc_number: Optional[str] = None
    aoc_expiry: Optional[date] = None
    fleet_size: int = 0
    primary_contact_id: Optional[uuid.UUID] = None
    ops_email: Optional[str] = None
    ops_phone: Optional[str] = None
    ops_24h_phone: Optional[str] = None
    accounts_email: Optional[str] = None
    website: Optional[str] = None
    insurance_expiry: Optional[date] = None
    insurance_limit_cents: Optional[int] = None
    w9_on_file: bool = False
    is_preferred: bool = False
    blocklist_reason: Optional[str] = None
    commission_rate: Optional[float] = None
    payment_terms: PaymentTerms = PaymentTerms.PREPAID
    notes: Optional[str] = None


class OperatorCreate(OperatorBase):
    pass


class OperatorUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    legal_name: Optional[str] = None
    dba_name: Optional[str] = None
    operator_code: Optional[str] = None
    status: Optional[OperatorStatus] = None
    country_code: Optional[str] = None
    regulatory_part: Optional[RegulatoryPart] = None
    aoc_number: Optional[str] = None
    aoc_expiry: Optional[date] = None
    fleet_size: Optional[int] = None
    primary_contact_id: Optional[uuid.UUID] = None
    ops_email: Optional[str] = None
    ops_phone: Optional[str] = None
    ops_24h_phone: Optional[str] = None
    accounts_email: Optional[str] = None
    website: Optional[str] = None
    insurance_expiry: Optional[date] = None
    insurance_limit_cents: Optional[int] = None
    w9_on_file: Optional[bool] = None
    is_preferred: Optional[bool] = None
    blocklist_reason: Optional[str] = None
    commission_rate: Optional[float] = None
    payment_terms: Optional[PaymentTerms] = None
    notes: Optional[str] = None


class OperatorRead(OperatorBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class OperatorList(BaseModel):
    items: list[OperatorRead]
    total: int
    page: int
    page_size: int


class OperatorSafetyRatingBase(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    operator_id: uuid.UUID
    program: SafetyProgram
    rating_level: SafetyRatingLevel
    rating_label: Optional[str] = None
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    audit_reference: Optional[str] = None
    auditor_name: Optional[str] = None
    scope_notes: Optional[str] = None
    is_current: bool = True
    report_document_id: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[uuid.UUID] = None


class OperatorSafetyRatingCreate(OperatorSafetyRatingBase):
    pass


class OperatorSafetyRatingUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    operator_id: Optional[uuid.UUID] = None
    program: Optional[SafetyProgram] = None
    rating_level: Optional[SafetyRatingLevel] = None
    rating_label: Optional[str] = None
    issued_date: Optional[date] = None
    expiry_date: Optional[date] = None
    audit_reference: Optional[str] = None
    auditor_name: Optional[str] = None
    scope_notes: Optional[str] = None
    is_current: Optional[bool] = None
    report_document_id: Optional[uuid.UUID] = None
    verified_at: Optional[datetime] = None
    verified_by_user_id: Optional[uuid.UUID] = None


class OperatorSafetyRatingRead(OperatorSafetyRatingBase):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)
    id: uuid.UUID
    client_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[uuid.UUID] = None
    updated_by: Optional[uuid.UUID] = None


class OperatorSafetyRatingList(BaseModel):
    items: list[OperatorSafetyRatingRead]
    total: int
    page: int
    page_size: int
