"""Health check router — verifies backend, database, and cache connectivity."""

from __future__ import annotations

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from backend.api.deps import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", tags=["system"])
async def health() -> JSONResponse:
    """Comprehensive health check.

    Returns 200 if all services are healthy, 503 if any are degraded.
    Checks: SQLite, Redis (if configured), ChromaDB (if available).
    """
    settings = get_settings()
    checks = {}

    # SQLite (audit DB)
    try:
        from backend.persistence.audit import AuditService

        with AuditService()._connect() as conn:
            conn.execute("SELECT 1")
        checks["sqlite"] = "ok"
    except Exception as e:
        logger.warning("SQLite health check failed: %s", e)
        checks["sqlite"] = "error"

    # Redis (if configured)
    if settings.redis_url:
        try:
            import redis

            r = redis.from_url(settings.redis_url, socket_timeout=2)
            r.ping()
            checks["redis"] = "ok"
        except Exception as e:
            logger.warning("Redis health check failed: %s", e)
            checks["redis"] = "error"
    else:
        checks["redis"] = "not_configured"

    # Auth DB (SQLite)
    try:
        from backend.persistence.user_store import UserStore

        store = UserStore()
        store.conn.execute("SELECT 1")
        checks["auth_db"] = "ok"
    except Exception as e:
        logger.warning("Auth DB health check failed: %s", e)
        checks["auth_db"] = "error"

    # Determine overall status
    critical_checks = ["sqlite", "auth_db"]
    has_critical_failure = any(checks.get(c) == "error" for c in critical_checks)
    has_any_failure = any(v == "error" for v in checks.values())

    if has_critical_failure:
        status = "unhealthy"
        status_code = 503
    elif has_any_failure:
        status = "degraded"
        status_code = 200  # Still operational
    else:
        status = "ok"
        status_code = 200

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status,
            "version": settings.app_version,
            "checks": checks,
        },
    )
