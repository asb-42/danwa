"""Tags API router — CRUD for tenant-global tag management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_tag_store
from backend.models.tag import (
    TagCreateRequest,
    TagResponse,
    TagUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tenants/{tenant_id}/tags", response_model=list[TagResponse])
def list_tags(
    tenant_id: str,
    store=Depends(get_tag_store),
) -> list[TagResponse]:
    """List all tags for a tenant."""
    tags = store.list_by_tenant(tenant_id)
    return [
        TagResponse(
            id=t.id,
            tenant_id=t.tenant_id,
            name=t.name,
            color=t.color,
            parent_id=t.parent_id,
            created_at=t.created_at,
        )
        for t in tags
    ]


@router.post("/tenants/{tenant_id}/tags", response_model=TagResponse, status_code=201)
def create_tag(
    tenant_id: str,
    body: TagCreateRequest,
    store=Depends(get_tag_store),
) -> TagResponse:
    """Create a new tag for a tenant."""
    tag = store.create(
        tenant_id=tenant_id,
        name=body.name,
        color=body.color,
        parent_id=body.parent_id,
    )
    return TagResponse(
        id=tag.id,
        tenant_id=tag.tenant_id,
        name=tag.name,
        color=tag.color,
        parent_id=tag.parent_id,
        created_at=tag.created_at,
    )


@router.get("/tenants/{tenant_id}/tags/{tag_id}", response_model=TagResponse)
def get_tag(
    tenant_id: str,
    tag_id: str,
    store=Depends(get_tag_store),
) -> TagResponse:
    """Get a single tag."""
    tag = store.get(tenant_id, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return TagResponse(
        id=tag.id,
        tenant_id=tag.tenant_id,
        name=tag.name,
        color=tag.color,
        parent_id=tag.parent_id,
        created_at=tag.created_at,
    )


@router.put("/tenants/{tenant_id}/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tenant_id: str,
    tag_id: str,
    body: TagUpdateRequest,
    store=Depends(get_tag_store),
) -> TagResponse:
    """Update a tag's name and/or color."""
    tag = store.update(
        tenant_id=tenant_id,
        tag_id=tag_id,
        name=body.name,
        color=body.color,
    )
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    return TagResponse(
        id=tag.id,
        tenant_id=tag.tenant_id,
        name=tag.name,
        color=tag.color,
        parent_id=tag.parent_id,
        created_at=tag.created_at,
    )


@router.delete("/tenants/{tenant_id}/tags/{tag_id}")
def delete_tag(
    tenant_id: str,
    tag_id: str,
    store=Depends(get_tag_store),
) -> dict:
    """Delete a tag."""
    tag = store.get(tenant_id, tag_id)
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    deleted = store.delete(tenant_id, tag_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete tag")
    return {"status": "ok", "deleted": tag_id}
