"""Tag model — tenant-global labels for case classification.

Tags are flat for MVP but reserve a ``parent_id`` field for future
hierarchical tag support.  Every tag belongs to exactly one tenant
and can be assigned to any number of cases within that tenant.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Tag(BaseModel):
    """A tenant-global tag for categorising cases."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = "_default"
    name: str = Field(..., min_length=1, max_length=100)
    color: str = "#6366f1"
    parent_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TagCreateRequest(BaseModel):
    """POST /api/v1/tenants/{tid}/tags request body."""

    name: str = Field(..., min_length=1, max_length=100)
    color: str = "#6366f1"
    parent_id: str | None = None


class TagUpdateRequest(BaseModel):
    """PUT /api/v1/tenants/{tid}/tags/{tagId} request body."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    color: str | None = None


class TagResponse(BaseModel):
    """Tag response model."""

    id: str
    tenant_id: str
    name: str
    color: str
    parent_id: str | None
    created_at: datetime
