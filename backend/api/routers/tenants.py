"""Tenant administration API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user, get_tenant_store, get_user_store
from backend.core.security import hash_password, user_to_response
from backend.models.tenant import TenantResponse, TenantUpdate
from backend.models.user import UserCreate, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/current", response_model=TenantResponse)
def get_current_tenant(
    user=Depends(get_current_user),
    tenant_store=Depends(get_tenant_store),
):
    """Get the current user's tenant."""
    tenant = tenant_store.get(user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantResponse(
        id=tenant.id,
        name=tenant.name,
        plan=tenant.plan,
        max_projects=tenant.max_projects,
        max_concurrent_debates=tenant.max_concurrent_debates,
        max_documents=tenant.max_documents,
        max_storage_mb=tenant.max_storage_mb,
        settings=tenant.settings,
        created_at=tenant.created_at,
        is_active=tenant.is_active,
    )


@router.put("/current/settings", response_model=TenantResponse)
def update_tenant_settings(
    body: TenantUpdate,
    user=Depends(get_current_user),
    tenant_store=Depends(get_tenant_store),
):
    """Update the current tenant's settings. Admin only."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    tenant = tenant_store.get(user.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    update_data = body.model_dump(exclude_none=True)
    updated = tenant_store.update(user.tenant_id, **update_data)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update tenant")

    return TenantResponse(
        id=updated.id,
        name=updated.name,
        plan=updated.plan,
        max_projects=updated.max_projects,
        max_concurrent_debates=updated.max_concurrent_debates,
        max_documents=updated.max_documents,
        max_storage_mb=updated.max_storage_mb,
        settings=updated.settings,
        created_at=updated.created_at,
        is_active=updated.is_active,
    )


@router.get("/current/users", response_model=list[UserResponse])
def list_tenant_users(
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """List all users in the current tenant. Admin only."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    users = user_store.list_by_tenant(user.tenant_id)
    return [user_to_response(u) for u in users]


@router.post("/current/invite", response_model=UserResponse, status_code=201)
def invite_user(
    body: UserCreate,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Invite a new user to the current tenant. Admin only."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    existing = user_store.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    new_user = user_store.create(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role,
        tenant_id=user.tenant_id,  # Force into the admin's tenant
    )

    logger.info("User invited to tenant %s: %s", user.tenant_id, new_user.email)
    return user_to_response(new_user)


@router.delete("/current/users/{target_user_id}")
def remove_user(
    target_user_id: str,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Remove a user from the current tenant. Admin only. Cannot remove yourself."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    if target_user_id == user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")

    target = user_store.get(target_user_id)
    if not target or target.tenant_id != user.tenant_id:
        raise HTTPException(status_code=404, detail="User not found")

    user_store.delete(target_user_id)
    logger.info("User %s removed from tenant %s", target_user_id, user.tenant_id)
    return {"status": "ok"}
