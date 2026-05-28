"""BYOK (Bring Your Own Key) API router — per-user LLM API key management."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class UserKeySetRequest(BaseModel):
    """Request to store a BYOK API key."""

    profile_id: str
    api_key: str = Field(..., min_length=1)
    label: str = ""


class UserKeyResponse(BaseModel):
    """Response for a stored BYOK key (key is masked)."""

    profile_id: str
    label: str
    has_key: bool
    created_at: str
    updated_at: str


@router.get("", response_model=list[UserKeyResponse])
def list_user_keys(
    user=Depends(get_current_user),
):
    """List all BYOK keys for the current user (keys are masked)."""
    from backend.persistence.user_key_store import UserKeyStore

    store = UserKeyStore()
    return store.list_keys(user.id)


@router.put("", response_model=UserKeyResponse)
def set_user_key(
    body: UserKeySetRequest,
    user=Depends(get_current_user),
):
    """Store or update a BYOK API key for a specific LLM profile.

    The key is stored per-user and takes precedence over the profile's
    environment variable when the user triggers an LLM call.
    """
    from backend.persistence.user_key_store import UserKeyStore

    store = UserKeyStore()
    store.set_key(user.id, body.profile_id, body.api_key, body.label)

    return UserKeyResponse(
        profile_id=body.profile_id,
        label=body.label,
        has_key=True,
        created_at="",
        updated_at="",
    )


@router.delete("/{profile_id}")
def delete_user_key(
    profile_id: str,
    user=Depends(get_current_user),
):
    """Delete a BYOK API key for a specific LLM profile."""
    from backend.persistence.user_key_store import UserKeyStore

    store = UserKeyStore()
    store.delete_key(user.id, profile_id)
    return {"status": "ok", "message": f"Key for profile {profile_id} deleted"}


@router.delete("")
def delete_all_user_keys(
    user=Depends(get_current_user),
):
    """Delete all BYOK API keys for the current user."""
    from backend.persistence.user_key_store import UserKeyStore

    store = UserKeyStore()
    count = store.delete_all_keys(user.id)
    return {"status": "ok", "deleted": count}
