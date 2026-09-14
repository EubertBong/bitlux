"""Shared response shapes."""

from __future__ import annotations

import re
from typing import Annotated, Any, Optional

from pydantic import AfterValidator, BaseModel, Field

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalise_email(v: str) -> str:
    """Trim + lower-case (the column is citext) and require the obvious shape.

    Deliberately not pydantic's EmailStr: email-validator rejects reserved TLDs
    such as ``.test`` and ``.local``, which is exactly what demo and staging
    tenants use. Deliverability is not this layer's concern.
    """
    v = v.strip().lower()
    if not _EMAIL.match(v):
        raise ValueError("must be a valid email address")
    return v


EmailAddress = Annotated[str, AfterValidator(_normalise_email)]


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(BaseModel):
    error: ErrorBody


class Deleted(BaseModel):
    id: str
    deleted: bool = True


class SearchHitOut(BaseModel):
    id: str
    type: str
    label: str
    subtitle: Optional[str] = None
    url: str
    rank: float


class SearchResponse(BaseModel):
    query: str
    results: dict[str, list[SearchHitOut]]


class GraphNode(BaseModel):
    id: str
    type: str
    label: str
    subtitle: Optional[str] = None
    url: str


class GraphEdge(BaseModel):
    from_: str = Field(alias="from", serialization_alias="from")
    to: str
    type: str
    label: str

    model_config = {"populate_by_name": True}


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
