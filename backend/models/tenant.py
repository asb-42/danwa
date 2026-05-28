"""Tenant model for multi-tenancy."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field


class Tenant(BaseModel):
    """Top-level organization entity. Users and projects belong to a tenant."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = Field(..., min_length=1, max_length=200)
    plan: Literal["free", "pro", "enterprise"] = "free"
    max_projects: int = 5
    max_concurrent_debates: int = 2
    max_documents: int = 50
    max_storage_mb: int = 500
    settings: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    is_active: bool = True


class TenantCreate(BaseModel):
    """Request model for creating a tenant."""

    name: str = Field(..., min_length=1, max_length=200)
    plan: Literal["free", "pro", "enterprise"] = "free"


class TenantUpdate(BaseModel):
    """Request model for updating tenant settings."""

    name: str | None = None
    plan: Literal["free", "pro", "enterprise"] | None = None
    max_projects: int | None = None
    max_concurrent_debates: int | None = None
    max_documents: int | None = None
    max_storage_mb: int | None = None
    settings: dict | None = None
    is_active: bool | None = None


class TenantResponse(BaseModel):
    """Public tenant data."""

    id: str
    name: str
    plan: str
    max_projects: int
    max_concurrent_debates: int
    max_documents: int
    max_storage_mb: int
    settings: dict
    created_at: datetime
    is_active: bool
