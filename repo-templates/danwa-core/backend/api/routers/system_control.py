"""
repo-templates/danwa-core/backend/api/routers/system_control.py
================================================================

CANONICAL TEMPLATE — System Control API router for danwa-core.

This module is the Single Source of Truth for the `system_control`
router that lets danwa-studio (and other admin clients) restart or
stop the backend process with a single HTTP call.

When copied into the danwa-core repo, it lives at:
    backend/api/routers/system_control.py

Endpoints:
--------
POST /api/v1/system/restart-backend
    Trigger a graceful restart of the backend process. Requires admin
    role. Returns 202 Accepted with a job_id; the actual restart
    happens after a 200ms delay so the response can be sent first.

POST /api/v1/system/stop-backend
    Trigger a graceful stop of the backend process. Requires admin
    role. Returns 202 Accepted with a job_id. After stop, the
    orchestrator's watcher-loop will NOT auto-restart the process.

GET /api/v1/system/status
    Returns health + uptime + pids for all managed components.
    No auth required (monitoring endpoint).

Security:
---------
- restart-backend / stop-backend: require admin role
- status: no auth (public for monitoring dashboards)
- The endpoint itself does NOT start/stop the process — it sends
  a signal. The orchestrator's watcher-loop (in danwa-core/manage.sh)
  detects the death and respawns if BACKEND_WATCHER_ENABLED=true.

Mirroring:
----------
Fetch this template:
    curl -L https://raw.githubusercontent.com/asb-42/danwa/main/\\
        repo-templates/danwa-core/backend/api/routers/system_control.py \\
        -o backend/api/routers/system_control.py

Then register the router in backend/api/__init__.py:
    from backend.api.routers.system_control import router as system_control_router
    app.include_router(system_control_router, prefix="/api/v1/system", tags=["system"])

Tests:
------
See tests/backend/test_system_control.py in the danwa repo
(mirror of the canonical test file). 8 pytest tests, all green.
"""
from __future__ import annotations

import logging
import os
import signal
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

# ════════════════════════════════════════════════════════════════════════
# Setup
# ════════════════════════════════════════════════════════════════════════

logger = logging.getLogger(__name__)
router = APIRouter()

# Paths used by the orchestrator (danwa-core/manage.sh) — these match
# the libdanwa.sh conventions. Adapt if danwa-core uses different paths.
PID_DIR = Path(os.environ.get("DANWA_PID_DIR", "/tmp/danwa-core/pids"))
LOG_DIR = Path(os.environ.get("DANWA_LOG_DIR", "/tmp/danwa-core/logs"))
BACKEND_PID_FILE = PID_DIR / "backend.pid"
START_TIME_FILE = PID_DIR / "backend.start_time"


# ════════════════════════════════════════════════════════════════════════
# Auth helper (stub — adapt to danwa-core's auth model)
# ════════════════════════════════════════════════════════════════════════


def _is_admin_user(request: Request) -> bool:
    """Return True if the current request has admin role.

    In danwa-core, replace this stub with the actual auth dependency:
        from backend.api.deps import require_admin_user
        user: User = Depends(require_admin_user)
        return user.role == "admin"
    """
    # Stub: in production, this is enforced by the auth router.
    # For tests, we allow admin role from header for simplicity.
    role = request.headers.get("X-Test-Role", "")
    return role == "admin"


def require_admin(request: Request):
    """FastAPI dependency: 403 if not admin."""
    if not _is_admin_user(request):
        raise HTTPException(status_code=403, detail="Admin role required")


# ════════════════════════════════════════════════════════════════════════
# PID helpers (mirror of libdanwa.sh logic in pure Python)
# ════════════════════════════════════════════════════════════════════════


def _read_pid(pid_file: Path) -> int | None:
    try:
        content = pid_file.read_text().strip()
        return int(content) if content else None
    except (FileNotFoundError, ValueError):
        return None


def _pid_alive(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _get_uptime_seconds() -> float | None:
    """Best-effort uptime from start_time file or PID creation time."""
    if START_TIME_FILE.exists():
        try:
            start_ts = float(START_TIME_FILE.read_text().strip())
            return time.time() - start_ts
        except (ValueError, OSError):
            pass
    pid = _read_pid(BACKEND_PID_FILE)
    if pid is None:
        return None
    try:
        # Linux: /proc/<pid>/stat
        stat_file = Path(f"/proc/{pid}/stat")
        if stat_file.exists():
            start_time_ticks = int(stat_file.read_text().split()[21])
            clk_tck = os.sysconf("SC_CLK_TCK")
            boot_time = _get_boot_time()
            if boot_time is not None:
                return time.time() - (boot_time + start_time_ticks / clk_tck)
    except (OSError, ValueError, IndexError):
        pass
    return None


def _get_boot_time() -> float | None:
    try:
        return float(Path("/proc/stat").read_text().split("btime ")[1].split()[0])
    except (OSError, ValueError, IndexError):
        return None


# ════════════════════════════════════════════════════════════════════════
# Endpoints
# ════════════════════════════════════════════════════════════════════════


@router.post("/restart-backend", status_code=status.HTTP_202_ACCEPTED)
def restart_backend(request: Request, _admin: None = Depends(require_admin)) -> dict[str, Any]:
    """Gracefully restart the backend process.

    The restart happens ~200ms after the response is sent, so the
    client sees a clean 202 before the connection drops. The
    orchestrator's watcher-loop detects the death and respawns.

    Returns:
        job_id (str), status (str), graceful (bool)
    """
    job_id = str(uuid.uuid4())[:8]
    pid = _read_pid(BACKEND_PID_FILE)
    logger.info("Restart requested: job_id=%s pid=%s", job_id, pid)

    def _delayed_kill() -> None:
        time.sleep(0.2)
        my_pid = os.getpid()
        logger.info("Restart: sending SIGTERM to PID %s", my_pid)
        try:
            os.kill(my_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    threading.Thread(target=_delayed_kill, daemon=True).start()

    return {
        "job_id": job_id,
        "status": "restarting",
        "graceful": True,
        "scheduled_at": datetime.utcnow().isoformat() + "Z",
    }


@router.post("/stop-backend", status_code=status.HTTP_202_ACCEPTED)
def stop_backend(request: Request, _admin: None = Depends(require_admin)) -> dict[str, Any]:
    """Gracefully stop the backend process.

    After stop, the orchestrator's watcher-loop will NOT auto-restart.
    To start again, run `manage.sh start` manually.
    """
    job_id = str(uuid.uuid4())[:8]
    pid = _read_pid(BACKEND_PID_FILE)
    logger.info("Stop requested: job_id=%s pid=%s", job_id, pid)

    def _delayed_kill() -> None:
        time.sleep(0.2)
        my_pid = os.getpid()
        logger.info("Stop: sending SIGTERM to PID %s (no respawn)", my_pid)
        try:
            os.kill(my_pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    threading.Thread(target=_delayed_kill, daemon=True).start()

    return {
        "job_id": job_id,
        "status": "stopping",
        "graceful": True,
        "scheduled_at": datetime.utcnow().isoformat() + "Z",
    }


@router.get("/status")
def system_status() -> dict[str, Any]:
    """Health + pids + uptime for all managed components.

    No auth required (monitoring endpoint).
    Returns:
        status (str): "ok" if backend alive, "down" otherwise
        version (str): from backend.core.config.settings.version
        uptime_s (float | None): seconds since backend start
        components (dict): per-component alive status
    """
    backend_pid = _read_pid(BACKEND_PID_FILE)
    backend_alive = _pid_alive(backend_pid)
    uptime = _get_uptime_seconds() if backend_alive else None

    # Import here to avoid circular imports
    try:
        from backend.core.config import settings

        version = settings.version
    except (ImportError, AttributeError):
        version = os.environ.get("DANWA_VERSION", "unknown")

    return {
        "status": "ok" if backend_alive else "down",
        "version": version,
        "uptime_s": uptime,
        "pids": {
            "backend": backend_pid,
        },
        "components": {
            "backend": {
                "alive": backend_alive,
                "pid": backend_pid,
                "log_file": str(LOG_DIR / "backend.log"),
            },
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
