"""Projects API router — list endpoint only.

.. deprecated::
    Projects are deprecated. Use tenants/cases instead.
    Only the list endpoint is retained for legacy move-to-project dialogs.
    All CRUD operations (create, update, delete, config) have been removed.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from backend.api.deps import get_current_user, get_project_store

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[dict])
def list_projects(
    store=Depends(get_project_store),
    user=Depends(get_current_user),
) -> list[dict]:
    """List projects scoped to the current user's tenant.

    .. deprecated::
        Use ``GET /api/v1/tenants/{tid}/cases`` instead.
    """
    projects = store.list_by_tenant(user.tenant_id)
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "is_system": p.is_system,
            "tenant_id": p.tenant_id,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        }
        for p in projects
    ]
