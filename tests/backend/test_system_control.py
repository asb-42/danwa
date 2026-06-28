"""
tests/backend/test_system_control.py
====================================

Tests for repo-templates/danwa-core/backend/api/routers/system_control.py
(mirror template — verify the contract here, then mirror to danwa-core
and run there as well).

Run from danwa root:
    uv run pytest tests/backend/test_system_control.py -v

The tests use FastAPI's TestClient + dependency_overrides to inject
a stub admin-user dep (matching the contract documented in the module).

8 tests cover:
- File presence (contract)
- /system/status returns health, pids, uptime
- /system/status requires no auth
- /system/restart-backend returns 202 with job_id
- /system/restart-backend requires admin (403 without)
- /system/restart-backend schedules a SIGTERM (verified via mocked signal)
- /system/stop-backend returns 202 with job_id
- /system/stop-backend requires admin (403 without)
"""

from __future__ import annotations

import os
import signal
import time
from pathlib import Path
from unittest import mock

import pytest
from fastapi import Request as FastAPIRequest

# ════════════════════════════════════════════════════════════════════════
# Contract tests (file structure + module surface)
# ════════════════════════════════════════════════════════════════════════


def test_system_control_module_exists_in_mirror_template():
    """The template file must exist at the canonical path."""
    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    assert template_path.exists(), f"Missing template: {template_path}"


def test_system_control_module_docstring_documented():
    """The module must have a top-level docstring documenting the API contract."""
    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    content = template_path.read_text()
    # Check the docstring mentions all 3 endpoints
    assert "/restart-backend" in content
    assert "/stop-backend" in content
    assert "/status" in content
    assert "admin" in content.lower(), "Docstring must mention admin auth"


# ════════════════════════════════════════════════════════════════════════
# Runtime tests (using TestClient with dependency overrides)
# ════════════════════════════════════════════════════════════════════════


@pytest.fixture
def client():
    """FastAPI TestClient with system_control router mounted at /api/v1/system."""
    # We load the module dynamically so we don't need danwa-core's full
    # FastAPI app (which has danwa-specific deps not available here).
    import importlib.util
    import sys

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control", template_path)
    module = importlib.util.module_from_spec(spec)

    # Stub the settings import that system_control.py does lazily
    sys.modules["backend"] = mock.MagicMock()
    sys.modules["backend.core"] = mock.MagicMock()
    sys.modules["backend.core.config"] = mock.MagicMock()
    sys.modules["backend.core.config"].settings = mock.MagicMock(version="0.3.0")

    spec.loader.exec_module(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")

    # Override the admin dep to use a header-based stub
    def stub_admin(request: FastAPIRequest):
        role = request.headers.get("X-Test-Role", "")
        if role != "admin":
            from fastapi import HTTPException

            raise HTTPException(status_code=403, detail="Admin role required")

    # Override by clearing dependencies on the routes
    app.dependency_overrides[module.require_admin] = stub_admin

    return TestClient(app)


def test_status_returns_health_pids_uptime_no_auth_required(client, tmp_path, monkeypatch):
    """GET /system/status returns health info, requires no auth."""
    # Set up PID file
    pid_dir = tmp_path / "pids"
    pid_dir.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    pid_file = pid_dir / "backend.pid"
    # Write our own PID (so the test process is "alive")
    pid_file.write_text(str(os.getpid()))
    (pid_dir / "backend.start_time").write_text(str(time.time() - 100))

    monkeypatch.setenv("DANWA_PID_DIR", str(pid_dir))
    monkeypatch.setenv("DANWA_LOG_DIR", str(log_dir))

    # Reload the module to pick up new env vars
    # (Easiest: re-import via importlib)
    import importlib.util

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v2", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")

    # Need to monkeypatch the module's PID_DIR
    module.PID_DIR = pid_dir
    module.LOG_DIR = log_dir
    module.BACKEND_PID_FILE = pid_dir / "backend.pid"
    module.START_TIME_FILE = pid_dir / "backend.start_time"

    client2 = TestClient(app)
    r = client2.get("/api/v1/system/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.3.0"
    assert data["uptime_s"] is not None
    assert data["uptime_s"] > 0
    assert data["components"]["backend"]["alive"] is True
    assert data["components"]["backend"]["pid"] == os.getpid()


def test_status_works_without_any_pids(client, tmp_path, monkeypatch):
    """GET /system/status with no PID files returns down status."""
    empty_pid_dir = tmp_path / "empty_pids"
    empty_pid_dir.mkdir()
    empty_log_dir = tmp_path / "empty_logs"
    empty_log_dir.mkdir()

    import importlib.util

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v3", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")
    module.PID_DIR = empty_pid_dir
    module.LOG_DIR = empty_log_dir

    client3 = TestClient(app)
    r = client3.get("/api/v1/system/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "down"
    assert data["uptime_s"] is None
    assert data["components"]["backend"]["alive"] is False
    assert data["components"]["backend"]["pid"] is None


def test_restart_backend_requires_admin(tmp_path):
    """POST /system/restart-backend without admin returns 403."""
    import importlib.util

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v4", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")

    client4 = TestClient(app)
    r = client4.post("/api/v1/system/restart-backend")
    assert r.status_code == 403
    assert "Admin" in r.json()["detail"]


def test_restart_backend_with_admin_returns_202(tmp_path):
    """POST /system/restart-backend with admin role returns 202 + job_id."""
    import importlib.util

    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v5", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def stub_admin(request: FastAPIRequest):
        role = request.headers.get("X-Test-Role", "")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")
    app.dependency_overrides[module.require_admin] = stub_admin

    client5 = TestClient(app)
    r = client5.post(
        "/api/v1/system/restart-backend",
        headers={"X-Test-Role": "admin"},
    )
    assert r.status_code == 202
    data = r.json()
    assert "job_id" in data
    assert len(data["job_id"]) == 8
    assert data["status"] == "restarting"
    assert data["graceful"] is True
    assert "scheduled_at" in data


def test_stop_backend_requires_admin(tmp_path):
    """POST /system/stop-backend without admin returns 403."""
    import importlib.util

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v6", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")

    client6 = TestClient(app)
    r = client6.post("/api/v1/system/stop-backend")
    assert r.status_code == 403


def test_stop_backend_with_admin_returns_202(tmp_path):
    """POST /system/stop-backend with admin role returns 202 + job_id."""
    import importlib.util

    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v7", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def stub_admin(request: FastAPIRequest):
        role = request.headers.get("X-Test-Role", "")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")
    app.dependency_overrides[module.require_admin] = stub_admin

    client7 = TestClient(app)
    r = client7.post(
        "/api/v1/system/stop-backend",
        headers={"X-Test-Role": "admin"},
    )
    assert r.status_code == 202
    data = r.json()
    assert data["status"] == "stopping"
    assert data["graceful"] is True


def test_restart_schedules_sigterm_with_delay(tmp_path):
    """Verify that restart_backend actually schedules a SIGTERM after ~200ms.

    We monkeypatch signal.SIGTERM handling to capture the call.
    """
    import importlib.util

    from fastapi import FastAPI, HTTPException
    from fastapi.testclient import TestClient

    template_path = Path(__file__).parent.parent.parent / "repo-templates" / "danwa-core" / "backend" / "api" / "routers" / "system_control.py"
    spec = importlib.util.spec_from_file_location("system_control_v8", template_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # Capture signal-related calls
    captured_signals = []

    def mock_kill(pid, sig):
        captured_signals.append((pid, sig))
        # Don't actually kill the test process
        if sig == signal.SIGTERM and pid != os.getpid():
            pass
        return None

    def stub_admin(request: FastAPIRequest):
        role = request.headers.get("X-Test-Role", "")
        if role != "admin":
            raise HTTPException(status_code=403, detail="Admin role required")

    app = FastAPI()
    app.include_router(module.router, prefix="/api/v1/system")
    app.dependency_overrides[module.require_admin] = stub_admin

    # Patch os.kill only in the module's namespace
    module.os.kill = mock_kill

    client8 = TestClient(app)
    r = client8.post(
        "/api/v1/system/restart-backend",
        headers={"X-Test-Role": "admin"},
    )
    assert r.status_code == 202

    # Wait for the delayed thread (200ms in module)
    time.sleep(0.4)

    # We should have captured a SIGTERM call
    assert any(s == signal.SIGTERM for _, s in captured_signals), f"Expected SIGTERM in captured signals: {captured_signals}"
