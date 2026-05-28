"""Tenant quota enforcement functions."""

from __future__ import annotations

import logging

from fastapi import HTTPException

from backend.models.tenant import Tenant

logger = logging.getLogger(__name__)


def check_debate_quota(tenant: Tenant, active_debate_count: int) -> None:
    """Raise 429 if tenant has reached concurrent debate limit."""
    if active_debate_count >= tenant.max_concurrent_debates:
        raise HTTPException(
            status_code=429,
            detail=f"Concurrent debate limit reached ({tenant.max_concurrent_debates}). Upgrade your plan or wait for a debate to complete.",
        )


def check_document_quota(tenant: Tenant, current_document_count: int) -> None:
    """Raise 429 if tenant has reached document limit."""
    if current_document_count >= tenant.max_documents:
        raise HTTPException(
            status_code=429,
            detail=f"Document limit reached ({tenant.max_documents}). Upgrade your plan or remove existing documents.",
        )


def check_project_quota(tenant: Tenant, current_project_count: int) -> None:
    """Raise 429 if tenant has reached project limit."""
    if current_project_count >= tenant.max_projects:
        raise HTTPException(
            status_code=429,
            detail=f"Project limit reached ({tenant.max_projects}). Upgrade your plan or remove existing projects.",
        )
