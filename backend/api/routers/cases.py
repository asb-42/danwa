"""Cases API router — CRUD for case management within a tenant."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_case_store
from backend.models.case import (
    CaseCreateRequest,
    CaseListItem,
    CaseResponse,
    CaseUpdateRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/tenants/{tenant_id}/cases", response_model=list[CaseListItem])
def list_cases(
    tenant_id: str,
    store=Depends(get_case_store),
) -> list[CaseListItem]:
    """List all cases in a tenant."""
    cases = store.list_by_tenant(tenant_id)
    return [
        CaseListItem(
            id=c.id,
            tenant_id=c.tenant_id,
            title=c.title,
            description=c.description,
            status=c.status,
            tags=c.tags,
            created_by=c.created_by,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in cases
    ]


@router.post("/tenants/{tenant_id}/cases", response_model=CaseResponse, status_code=201)
def create_case(
    tenant_id: str,
    body: CaseCreateRequest,
    store=Depends(get_case_store),
) -> CaseResponse:
    """Create a new case within a tenant."""
    case = store.create(
        tenant_id=tenant_id,
        title=body.title,
        description=body.description,
        tags=body.tags,
        created_by=body.created_by,
    )
    return CaseResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        title=case.title,
        description=case.description,
        status=case.status,
        tags=case.tags,
        created_by=case.created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
        metadata=case.metadata,
    )


@router.get("/tenants/{tenant_id}/cases/{case_id}", response_model=CaseResponse)
def get_case(
    tenant_id: str,
    case_id: str,
    store=Depends(get_case_store),
) -> CaseResponse:
    """Get case details."""
    case = store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        title=case.title,
        description=case.description,
        status=case.status,
        tags=case.tags,
        created_by=case.created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
        metadata=case.metadata,
    )


@router.patch("/tenants/{tenant_id}/cases/{case_id}", response_model=CaseResponse)
def update_case(
    tenant_id: str,
    case_id: str,
    body: CaseUpdateRequest,
    store=Depends(get_case_store),
) -> CaseResponse:
    """Update case fields (title, description, tags, status)."""
    kwargs = {}
    if body.title is not None:
        kwargs["title"] = body.title
    if body.description is not None:
        kwargs["description"] = body.description
    if body.tags is not None:
        kwargs["tags"] = body.tags
    if body.status is not None:
        kwargs["status"] = body.status

    case = store.update(tenant_id, case_id, **kwargs)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return CaseResponse(
        id=case.id,
        tenant_id=case.tenant_id,
        title=case.title,
        description=case.description,
        status=case.status,
        tags=case.tags,
        created_by=case.created_by,
        created_at=case.created_at,
        updated_at=case.updated_at,
        metadata=case.metadata,
    )


@router.delete("/tenants/{tenant_id}/cases/{case_id}")
def delete_case(
    tenant_id: str,
    case_id: str,
    store=Depends(get_case_store),
) -> dict:
    """Delete a case. System default cases cannot be deleted."""
    case = store.get(tenant_id, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    if case_id == "_default":
        raise HTTPException(status_code=403, detail="Cannot delete default case")
    deleted = store.delete(tenant_id, case_id)
    if not deleted:
        raise HTTPException(status_code=500, detail="Failed to delete case")
    return {"status": "ok", "deleted": case_id}
