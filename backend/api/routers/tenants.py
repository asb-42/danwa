"""Tenant administration API router."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_current_user, get_membership_store, get_tenant_store, get_user_store
from backend.core.security import hash_password, user_to_response
from backend.models.tenant import TenantCreate, TenantResponse, TenantUpdate
from backend.models.user import UserCreate, UserResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=list[TenantResponse])
def list_all_tenants(
    user=Depends(get_current_user),
    tenant_store=Depends(get_tenant_store),
) -> list[TenantResponse]:
    """List all tenants. Admin only."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    tenants = tenant_store.list_all()
    return [
        TenantResponse(
            id=t.id,
            name=t.name,
            plan=t.plan,
            max_projects=t.max_projects,
            max_concurrent_debates=t.max_concurrent_debates,
            max_documents=t.max_documents,
            max_storage_mb=t.max_storage_mb,
            settings=t.settings,
            created_at=t.created_at,
            is_active=t.is_active,
        )
        for t in tenants
    ]


@router.post("/", response_model=TenantResponse, status_code=201)
def create_tenant(
    body: TenantCreate,
    user=Depends(get_current_user),
    tenant_store=Depends(get_tenant_store),
    membership_store=Depends(get_membership_store),
) -> TenantResponse:
    """Create a new tenant. Admin only. Creator gets owner membership."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    tenant = tenant_store.create(name=body.name, plan=body.plan)
    # Auto-add the creator as owner of the new tenant
    membership_store.add(tenant.id, user.id, role="admin", invited_by=None)
    logger.info("Tenant created: %s (%s) by user %s", tenant.name, tenant.id, user.email)
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
    membership_store=Depends(get_membership_store),
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

    # Ensure the invited user has a membership in this tenant.
    membership_store.add(user.tenant_id, new_user.id, role=body.role, invited_by=user.id)

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
