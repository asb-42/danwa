"""Authentication API router — login, register, refresh, me, password change."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from jose import JWTError

from backend.api.deps import get_current_user, get_user_store, require_role
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    user_to_response,
    verify_password,
)
from backend.models.user import (
    LoginRequest,
    PasswordChangeRequest,
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
):
    """Register a new user (self-signup). First user is auto-promoted to admin."""
    existing = user_store.get_by_email(body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    # First user becomes admin automatically
    role = body.role
    if user_store.count() == 0:
        role = "admin"
        logger.info("First user registered — promoting to admin: %s", body.email)

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
    body: dict,
    user=Depends(get_current_user),
    user_store=Depends(get_user_store),
):
    """Update the current user's profile (display_name)."""
    display_name = body.get("display_name")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")

    updated = user_store.update(user.id, display_name=display_name)
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update profile")

    logger.info("Profile updated for user: %s", user.email)
    return user_to_response(updated)


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
