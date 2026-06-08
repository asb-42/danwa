"""TenantMembership model — user membership in a tenant with role."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class TenantMembership(BaseModel):
    """A user's membership in a specific tenant with a role."""

    tenant_id: str
    user_id: str
    role: str = "member"  # admin | member | viewer
    invited_by: str | None = None
    joined_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class TenantMembershipResponse(BaseModel):
    """Public membership data."""

    tenant_id: str
    user_id: str
    role: str
    invited_by: str | None
    joined_at: datetime
    tenant_name: str | None = None
