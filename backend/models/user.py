"""User model for multi-user authentication."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class User(BaseModel):
    """Persistent user with role-based access control."""

    id: str
    email: str
    display_name: str
    password_hash: str
    role: Literal["admin", "editor", "viewer"] = "viewer"
    tenant_id: str = "_default"
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    last_login_at: datetime | None = None


class UserCreate(BaseModel):
    """Request model for creating a user."""

    email: str
    display_name: str
    password: str = Field(min_length=8)
    role: Literal["admin", "editor", "viewer"] = "viewer"
    tenant_id: str = "_default"


class ProfileUpdateRequest(BaseModel):
    """Request model for self-service profile update (PUT /me)."""

    display_name: str = Field(min_length=1, max_length=200)


class UserUpdate(BaseModel):
    """Request model for admin-updating a user."""

    display_name: str | None = None
    role: Literal["admin", "editor", "viewer"] = None
    is_active: bool | None = None


class UserResponse(BaseModel):
    """Public user data (no password hash)."""

    id: str
    email: str
    display_name: str
    role: str
    tenant_id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    """Login credentials."""

    email: str
    password: str


class TokenResponse(BaseModel):
    """JWT token pair returned on login."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class RefreshRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str
    new_password: str = Field(min_length=8)
