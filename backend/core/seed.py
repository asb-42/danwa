"""Seed default tenant and admin user on first startup."""

from __future__ import annotations

import logging

from backend.persistence.tenant_store import TenantStore
from backend.persistence.user_store import UserStore

logger = logging.getLogger(__name__)


def ensure_default_tenant() -> None:
    """Create the default tenant if no tenants exist yet.

    Called during application startup. Idempotent.
    """
    store = TenantStore()
    if store.count() > 0:
        return

    logger.info("No tenants found — creating default tenant")
    store.create(name="Default", plan="free", tenant_id="_default")
    logger.info("Default tenant created (_default)")


def ensure_admin_user() -> None:
    """Create a default admin user if no users exist yet.

    Called during application startup. Idempotent — no-op if users already exist.
    """
    from backend.core.security import hash_password

    store = UserStore()
    if store.count() > 0:
        return

    # Ensure default tenant exists first
    ensure_default_tenant()

    logger.info("No users found — creating default admin user (admin@danwa.local / changeme)")
    store.create(
        email="admin@danwa.local",
        display_name="Admin",
        password_hash=hash_password("changeme"),
        role="admin",
        tenant_id="_default",
    )
    logger.info("Default admin user created. CHANGE THE PASSWORD on first login!")
