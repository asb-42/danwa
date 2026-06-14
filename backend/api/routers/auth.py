"""Authentication API router — login, register, refresh, me, password change."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError

from backend.api.deps import get_current_user, get_membership_store, get_settings, get_tenant_store, get_user_store, require_role
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    user_to_response,
    verify_password,
)
from backend.models.membership import TenantMembershipResponse
from backend.models.user import (
    LoginRequest,
    PasswordChangeRequest,
    ProfileUpdateRequest,
    RefreshRequest,
    TokenResponse,
    UserCreate,
    UserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=201)
def register_user(
    body: UserCreate,
    user_store=Depends(get_user_store),
    membership_store=Depends(get_membership_store),
):
    """Register a new user (self-signup). First user is auto-promoted to admin."""
    existing = user_store.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # Drupal-style UID-1 mechanism: promote to admin if no admin exists yet.
    # This covers two cases:
    #   1. Fresh install — first user ever becomes admin.
    #   2. Existing install where the seeded admin was deleted — next
    #      registrant recovers admin access.
    role = "viewer"
    if user_store.count() == 0 or not user_store.has_admin():
        role = "admin"
        logger.info("No admin exists — promoting new user to admin: %s", body.email)

    password_hash = hash_password(body.password)

    # Self-signup always creates user in _default tenant
    try:
        user = user_store.create(
            email=body.email,
            display_name=body.display_name,
            password_hash=password_hash,
            role=role,
            tenant_id="_default",
        )
    except Exception as e:
        logger.error("Failed to create user %s: %s", body.email, e)
        raise HTTPException(status_code=500, detail="Failed to create user")

    # Ensure the user has a membership in the _default tenant so they
    # appear in the TenantSelector dropdown.
    membership_store.add("_default", user.id, role="admin" if role == "admin" else "member")

    logger.info("User registered: %s (role=%s)", user.email, user.role)
    return user_to_response(user)


@router.post("/login", response_model=TokenResponse)
def login(
    body: LoginRequest,
    user_store=Depends(get_user_store),
):
    """Authenticate with email + password. Returns JWT token pair."""
    user = user_store.get_by_email(body.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    user_store.update_last_login(user.id)

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    logger.info("User logged in: %s", user.email)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_token(
    body: RefreshRequest,
    user_store=Depends(get_user_store),
):
    """Exchange a refresh token for a new access + refresh token pair."""
    try:
        token_data = decode_token(body.refresh_token)
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid refresh token: {e}")

    if token_data.token_type != "refresh":
        raise HTTPException(status_code=401, detail="Token is not a refresh token")

    user = user_store.get(token_data.user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    access_token = create_access_token(user)
    refresh_token = create_refresh_token(user)

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(
    user=Depends(get_current_user),
):
    """Get the current authenticated user's profile."""
    return user_to_response(user)


@router.put("/me", response_model=UserResponse)
def update_me(
    body: ProfileUpdateRequest,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Update the current user's profile (display_name).

    S-03 fix: uses a typed Pydantic model instead of raw dict for
    input validation (min_length=1, max_length=200 on display_name).
    """
    updated = user_store.update(user.id, display_name=body.display_name.strip())
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")

    logger.info("Profile updated for user: %s", user.email)
    return user_to_response(updated)


# ─── Last-workspace setting (Case-Space Phase 1.3) ─────────────
# These endpoints let the frontend remember which Case the user
# had open at logout, and restore it on next login.  Storing a
# single string column keeps the GET /me call cheap (no JSON
# parse).  See plans/2026-06-14_case-space-workspace.md §4.2.


@router.get("/me/last-workspace")
def get_last_workspace(
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Return the case id the current user last opened, or null."""
    return {"case_id": user_store.get_last_workspace(user.id)}


@router.put("/me/last-workspace")
def set_last_workspace(
    body: dict,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Persist (or clear) the case id the user last opened.

    Body: ``{"case_id": "..."}`` to set, or ``{"case_id": null}`` to clear.
    Returns 204 on success.
    """
    case_id = body.get("case_id")
    if case_id is not None and not isinstance(case_id, str):
        raise HTTPException(status_code=422, detail="case_id must be a string or null")
    if case_id is not None and len(case_id) > 200:
        raise HTTPException(status_code=422, detail="case_id too long")
    ok = user_store.set_last_workspace(user.id, case_id)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to persist last_workspace")
    return {"case_id": case_id}


@router.put("/password")
def change_password(
    body: PasswordChangeRequest,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Change the current user's password."""
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    new_hash = hash_password(body.new_password)
    user_store.update(user.id, password_hash=new_hash)

    logger.info("Password changed for user: %s", user.email)
    return {"status": "ok", "message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# Admin-only user management endpoints
# ---------------------------------------------------------------------------


@router.get("/users", response_model=list[UserResponse])
def list_users(
    user_store=Depends(get_user_store),
    _=Depends(require_role("admin")),
):
    """List all registered users (admin only)."""
    return [user_to_response(u) for u in user_store.list_all()]


@router.post("/users/invite", response_model=UserResponse, status_code=201)
def invite_user(
    body: UserCreate,
    user_store=Depends(get_user_store),
    membership_store=Depends(get_membership_store),
    _=Depends(require_role("admin")),
):
    """Invite a new user by creating their account with a password (admin only)."""
    existing = user_store.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    password_hash = hash_password(body.password)
    try:
        user = user_store.create(
            email=body.email,
            display_name=body.display_name,
            password_hash=password_hash,
            role=body.role,
            tenant_id="_default",
        )
    except Exception as e:
        logger.error("Failed to create user %s: %s", body.email, e)
        raise HTTPException(status_code=500, detail="Failed to create user")

    # Ensure the invited user has a membership in the _default tenant.
    membership_store.add("_default", user.id, role=body.role if body.role in ("admin",) else "member")

    logger.info("User invited: %s (role=%s) by admin", user.email, user.role)
    return user_to_response(user)


@router.delete("/users/{user_id}", status_code=204)
def delete_user(
    user_id: str,
    user_store=Depends(get_user_store),
    current_user=Depends(require_role("admin")),
):
    """Delete a user account (admin only). Cannot delete yourself."""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    user = user_store.get(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user_store.delete(user_id)
    logger.info("User deleted: %s by admin %s", user.email, current_user.email)


# ---------------------------------------------------------------------------
# Multi-tenant endpoints
# ---------------------------------------------------------------------------


@router.get("/my-tenants", response_model=list[TenantMembershipResponse])
def list_my_tenants(
    user=Depends(get_current_user),
    membership_store=Depends(get_membership_store),
    tenant_store=Depends(get_tenant_store),
    settings=Depends(get_settings),
):
    """List all tenants the current user belongs to."""
    from datetime import UTC, datetime

    memberships = membership_store.list_by_user(user.id)

    # Dev mode (auth disabled): the synthetic dev-user has no memberships
    # in the DB.  Return all tenants as admin memberships so the
    # TenantSelector works without authentication.
    if not settings.auth_enabled and not memberships:
        all_tenants = tenant_store.list_all()
        now = datetime.now(UTC)
        return [
            TenantMembershipResponse(
                tenant_id=t.id,
                user_id=user.id,
                role="admin",
                invited_by=None,
                joined_at=now,
                tenant_name=t.name,
            )
            for t in all_tenants
        ]

    # Build a cache of tenant_id -> name for enrichment
    tenant_names: dict[str, str] = {}
    for m in memberships:
        if m.tenant_id not in tenant_names:
            tenant = tenant_store.get(m.tenant_id)
            tenant_names[m.tenant_id] = tenant.name if tenant else m.tenant_id
    return [
        TenantMembershipResponse(
            tenant_id=m.tenant_id,
            user_id=m.user_id,
            role=m.role,
            invited_by=m.invited_by,
            joined_at=m.joined_at,
            tenant_name=tenant_names.get(m.tenant_id),
        )
        for m in memberships
    ]


@router.post("/select-tenant/{tenant_id}", response_model=TokenResponse)
def select_tenant(
    tenant_id: str,
    user=Depends(get_current_user),
    membership_store=Depends(get_membership_store),
    settings=Depends(get_settings),
):
    """Switch the current user's active tenant.

    Validates membership and returns a new JWT token pair with the
    selected tenant_id embedded. The new token should be used for
    subsequent API requests.
    """
    membership = membership_store.get(tenant_id, user.id)

    # Dev mode (auth disabled): allow switching to any tenant as admin.
    if not membership and not settings.auth_enabled:
        role_override = "admin"
    elif not membership:
        raise HTTPException(status_code=403, detail="Not a member of this tenant")
    else:
        # S-05 fix: use the tenant-specific role from the membership,
        # not the user's global role, so a global admin is not
        # automatically admin in every tenant.
        role_override = membership.role

    access_token = create_access_token(
        user,
        tenant_id=tenant_id,
        role_override=role_override,
    )
    refresh_token = create_refresh_token(user)

    logger.info("User %s switched to tenant %s (role=%s)", user.email, tenant_id, role_override)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=user_to_response(user),
    )
