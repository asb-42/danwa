"""Case model — a self-contained matter/case within a tenant.

Every case has its own isolated DMS (documents, vector store) and debates.
Cases replace the flat ``Project`` model with tenant-scoped, taggable units.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Case(BaseModel):
    """A self-contained case/matter within a tenant."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "_default"
    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    status: str = "active"  # active | archived | closed
    tags: list[str] = Field(default_factory=list)
    created_by: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict = Field(default_factory=dict)


class CaseCreateRequest(BaseModel):
    """POST /api/v1/tenants/{tid}/cases request body."""

    title: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    created_by: str = ""


class CaseUpdateRequest(BaseModel):
    """PATCH /api/v1/tenants/{tid}/cases/{cid} request body."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    tags: list[str] | None = None
    status: str | None = None


class CaseResponse(BaseModel):
    """GET /api/v1/tenants/{tid}/cases/{cid} response."""

    id: str
    tenant_id: str
    title: str
    description: str
    status: str
    tags: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
    metadata: dict


class CaseListItem(BaseModel):
    """Lightweight case summary for list views."""

    id: str
    tenant_id: str
    title: str
    description: str
    status: str
    tags: list[str]
    created_by: str
    created_at: datetime
    updated_at: datetime
