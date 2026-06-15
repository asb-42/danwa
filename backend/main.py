"""FastAPI application entry point for Danwa Debate Engine.

Version and application metadata are loaded dynamically from
the ``/version`` file via ``settings.app_version``.
"""

from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# Load .env file into os.environ BEFORE any module reads os.getenv()
load_dotenv()

from fastapi import FastAPI  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402

from backend.a2a.router import router as a2a_router  # noqa: E402
from backend.api.deps import get_settings  # noqa: E402
from backend.api.routers import (  # noqa: E402
    a2a_discovery,
    argumentation_patterns,
    assistant,
    audit,
    auth,
    blueprint_events,
    blueprints,
    bundle_composer,
    canvas,
    cases,
    config,
    debate,
    debate_stream,
    dms,
    graph,
    health,
    inbox,
    input_composer,
    llm_profiles,
    modules,
    monitor,
    onboarding,
    optimization_proposals,
    output_composer,
    profiles,
    projects,
    sessions,
    system,
    tags,
    tenants,
    tone_profiles,
    user_keys,
    workflow_definitions,
    workflow_exec,
    workflow_reports,
    workflow_templates,
    workspace,
)
from backend.api.routers.case_scoped import router as case_scoped_router  # noqa: E402
from backend.api.routers.translation import router as translation_router  # noqa: E402
from backend.api.routers.ui_i18n import router as ui_i18n_router  # noqa: E402
from backend.workflow.hitl.api import router as hitl_router  # noqa: E402

# Path to built frontend assets (relative to project root)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
_LOG_DIR = Path(__file__).resolve().parent.parent / "logs"

logger = logging.getLogger(__name__)


def _setup_logging() -> None:
    """Configure application logging with file + console handlers.

    The log file is truncated on each application restart to prevent
    unbounded growth.  A ``RotatingFileHandler`` provides an additional
    safety net (10 MB max, 3 backups).
    """
    from logging.handlers import RotatingFileHandler

    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = _LOG_DIR / "debate-agent.log"

    # Truncate log file on restart
    try:
        log_file.write_text("", encoding="utf-8")
    except OSError:
        pass  # ignore if file doesn't exist yet

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # File handler — detailed, with timestamps, rotating at 10 MB
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    # Console handler — INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )
    )

    # Clear existing handlers (uvicorn adds its own) and add ours
    root_logger.handlers.clear()
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("litellm").setLevel(logging.WARNING)
    logging.getLogger("python_multipart").setLevel(logging.WARNING)
    logging.getLogger("chromadb").setLevel(logging.WARNING)
    logging.getLogger("chromadb.utils.embedding_functions").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    _setup_logging()

    # Setup structured logging (structlog)
    from backend.core.config import settings as _settings
    from backend.core.logging import setup_logging

    setup_logging(debug=_settings.debug)

    logger.info("Debate Engine starting up...")

    settings = get_settings()
    # Ensure DB directory exists
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)

    # Load settings from YAML file (overrides .env defaults)
    from backend.api.routers.config import _load_settings as _load_yaml_settings

    yaml_settings = _load_yaml_settings()
    if yaml_settings.get("backup"):
        for key, value in yaml_settings["backup"].items():
            if hasattr(settings, key):
                setattr(settings, key, value)
    if yaml_settings.get("ui"):
        ui_lang = yaml_settings["ui"].get("language")
        if ui_lang and hasattr(settings, "ui_language"):
            settings.ui_language = ui_lang
    if yaml_settings.get("utility_llm"):
        svc_llm_id = yaml_settings["utility_llm"].get("service_llm_profile_id")
        if svc_llm_id and hasattr(settings, "service_llm_profile_id"):
            settings.service_llm_profile_id = svc_llm_id

    logger.info("Settings loaded from config/settings.yaml")

    # Run project migration (idempotent)
    from backend.migrations.migrate_projects import migrate_to_projects

    migrate_to_projects()

    # Run multi-tenant migration (idempotent)
    from backend.migrations.v001_multi_tenant import migrate_to_multi_tenant

    migrate_to_multi_tenant()

    # Run v002 case-path migration (idempotent)
    from backend.migrations.v002_case_pfade import migrate_to_case_paths

    migrate_to_case_paths()

    # Run v003 graph-edge-cache migration (idempotent, Phase 4.3/5.2)
    from backend.migrations.v003_graph_edge_cache import migrate_graph_edge_cache

    migrate_graph_edge_cache()

    # Seed system workflow templates (idempotent)
    from scripts.seed_templates import seed_system_templates

    seed_system_templates()

    # Seed system tone profiles (idempotent)
    from scripts.seed_tone_profiles import seed_system_tone_profiles

    seed_system_tone_profiles()

    # Import modules into DB on startup (idempotent)
    from scripts.deploy_import import main as deploy_import_main

    deploy_import_main()

    # Migrate away from legacy seeded admin user (admin@danwa.local).
    # If the seed admin exists and real users are present, promote the
    # first real user to admin and delete the seed.
    try:
        _migrate_seed_admin()
    except Exception:
        logger.debug("Seed admin migration skipped", exc_info=True)

    # Security check: warn if auth is enabled but JWT secret is empty
    if settings.auth_enabled and not settings.jwt_secret_key:
        logger.critical(
            "SECURITY: auth_enabled=True but jwt_secret_key is empty! "
            "Set DANWA_JWT_SECRET_KEY in .env — tokens signed with an "
            "empty key are trivially forgeable. Disabling auth as fallback."
        )
        settings.auth_enabled = False

    # Seed default tenant (idempotent)
    from backend.core.seed import ensure_default_tenant

    ensure_default_tenant()

    # Backfill missing tenant memberships for existing users (idempotent).
    # Users created before the membership system have a tenant_id on the
    # user row but no matching entry in the memberships table.
    try:
        _backfill_memberships()
    except Exception:
        logger.debug("Membership backfill skipped", exc_info=True)

    # Reset stale "running" debates that survived a previous crash/restart.
    try:
        _reset_stale_running_debates()
    except Exception:
        logger.debug("Stale debate cleanup skipped", exc_info=True)

    # Bootstrap i18n: migrate core locale translations to langpack namespace (idempotent)
    from backend.services.ui_translation_service import UITranslationService

    try:
        i18n_svc = UITranslationService()
        i18n_svc.bootstrap_core_locales()
    except Exception as exc:
        logger.warning("i18n bootstrap skipped: %s", exc)

    # Clean up legacy local langpack directories (lp-* zombies from old bootstrap).
    # The danwa-modules repo is the single source of truth for language packs.
    try:
        i18n_svc.cleanup_legacy_local_langpacks()
    except Exception as exc:
        logger.warning("Legacy langpack cleanup skipped: %s", exc)

    yield
    logger.info("Debate Engine shutting down.")

    # --- Shutdown-Backup (Sprint 18) ---
    try:
        from backend.core.config import settings as s

        if s.backup_auto_on_shutdown:
            from backend.persistence.backup import BackupService

            service = BackupService()
            result = service.create_backup(trigger="shutdown")
            logger.info(
                "Shutdown-Backup erstellt: %s (%d Dateien, %d Bytes)",
                result.path,
                result.file_count,
                result.size_bytes,
            )
    except Exception as exc:
        logger.error("Shutdown-Backup fehlgeschlagen: %s", exc)


def _migrate_seed_admin() -> None:
    """One-time migration: remove legacy seed admin and promote first real user.

    If ``admin@danwa.local`` exists as the only admin and other users
    are present, the first non-seed user is promoted to admin and the
    seed admin is deleted.  Idempotent — no-op if seed admin is gone.
    """
    from backend.persistence.user_store import UserStore

    store = UserStore()
    seed = store.get_by_email("admin@danwa.local")
    if not seed:
        return  # nothing to migrate

    all_users = store.list_all()
    real_users = [u for u in all_users if u.email != "admin@danwa.local"]
    if not real_users:
        return  # only the seed admin exists; leave it until someone registers

    # Promote the first real user to admin
    first_user = min(real_users, key=lambda u: u.created_at)
    if first_user.role != "admin":
        store.update(first_user.id, role="admin")
        logger.info(
            "Seed admin migration: promoted %s to admin",
            first_user.email,
        )

    # Delete the seed admin
    store.delete(seed.id)
    logger.info("Seed admin migration: removed admin@danwa.local")


def _backfill_memberships() -> None:
    """Backfill missing tenant memberships for existing users.

    Users created before the membership system may have a ``tenant_id``
    on the user record but no corresponding row in the ``memberships``
    table.  This migration ensures every active user has at least one
    membership for their ``tenant_id``.  Admin users additionally get
    memberships in ALL existing tenants so they can access every tenant
    from the TenantSelector.  Idempotent — uses INSERT OR REPLACE.
    """
    from backend.persistence.membership_store import MembershipStore
    from backend.persistence.tenant_store import TenantStore
    from backend.persistence.user_store import UserStore

    user_store = UserStore()
    membership_store = MembershipStore()
    tenant_store = TenantStore()

    all_users = user_store.list_all()
    all_tenants = tenant_store.list_all()
    backfilled = 0
    for u in all_users:
        # Step 1: ensure membership for user's own tenant_id
        existing = membership_store.get(u.tenant_id, u.id)
        if not existing:
            role = "admin" if u.role == "admin" else "member"
            membership_store.add(u.tenant_id, u.id, role=role)
            backfilled += 1

        # Step 2: admin users get memberships in ALL tenants
        if u.role == "admin":
            for tenant in all_tenants:
                existing = membership_store.get(tenant.id, u.id)
                if not existing:
                    membership_store.add(tenant.id, u.id, role="admin")
                    backfilled += 1

    if backfilled:
        logger.info("Membership backfill: created %d membership(s)", backfilled)


def _reset_stale_running_debates() -> None:
    """Reset debates stuck in 'running' state from a previous crash or restart.

    On startup any debate still marked 'running' is presumed dead (the
    previous process was killed before it could update the status).
    Resets them to 'failed' so the dashboard counter is accurate and
    the tenant quota is released.
    """
    from datetime import UTC, datetime

    from backend.models.schemas import DebateStatus
    from backend.persistence.debate_store import DebateStore

    store = DebateStore()
    stale = store.list_by_status(DebateStatus.RUNNING)
    if not stale:
        return

    now = datetime.now(UTC)
    for d in stale:
        debate_id = d.get("debate_id", "unknown")
        store.update(
            debate_id,
            status=DebateStatus.FAILED,
            updated_at=now,
            result={"error": "Reset on startup: debate was stuck in 'running' state"},
        )
        logger.warning("Reset stale running debate %s to 'failed'", debate_id)

    logger.info("Startup cleanup: reset %d stale running debate(s) to 'failed'", len(stale))


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "Danwa — Auditierbarer Multi-Agenten-Debatten-Workflow.\n\n"
            "KI-gestützte Debattenplattform mit Multi-Tenant-Authentifizierung, "
            "RAG-Dokumentenanalyse, paralleler Workflow-Ausführung und "
            "strukturierter Berichterstellung.\n\n"
            "**Authentifizierung:** JWT Bearer Token via `/api/v1/auth/login`.\n\n"
            "**Dokumentation:** [Swagger UI](/docs) · [ReDoc](/redoc) · [OpenAPI JSON](/openapi.json)"
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Rate Limiting (slowapi) ---
    if settings.rate_limit_enabled:
        from slowapi import Limiter
        from slowapi.errors import RateLimitExceeded
        from slowapi.util import get_remote_address

        from backend.api.errors import _rate_limit_handler

        storage_uri = settings.redis_url if settings.redis_url else "memory://"
        limiter = Limiter(
            key_func=get_remote_address,
            storage_uri=storage_uri,
            default_limits=[settings.rate_limit_default],
        )
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)

    # --- Request-ID Middleware ---
    @app.middleware("http")
    async def add_request_context(request, call_next):
        """Add request context the instance."""
        import uuid as _uuid

        from backend.core.logging import bind_request_context

        request_id = request.headers.get("X-Request-ID", str(_uuid.uuid4()))
        bind_request_context(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    # --- Deprecation Headers for Legacy Routes ---
    legacy_route_deprecation = {
        "/api/v1/debate": "Use /api/v1/tenants/{tid}/cases/{cid}/debates/ instead.",
        "/api/v1/dms": "Use /api/v1/tenants/{tid}/cases/{cid}/dms/ instead.",
        "/api/v1/audit": "Use /api/v1/tenants/{tid}/cases/{cid}/audit/ instead.",
        "/api/v1/projects": "Projects are deprecated. Use tenants/cases instead.",
        "/api/v1/input": "Use /api/v1/tenants/{tid}/cases/{cid}/input/ instead.",
        "/api/v1/sessions": "Use /api/v1/tenants/{tid}/cases/{cid}/sessions/ instead.",
    }

    @app.middleware("http")
    async def add_deprecation_headers(request, call_next):
        """Add X-Deprecation header to responses from legacy (pre-tenant) routes."""
        response = await call_next(request)
        path = request.url.path.rstrip("/")
        for prefix, notice in legacy_route_deprecation.items():
            if path == prefix or path.startswith(prefix + "/"):
                response.headers["X-Deprecation"] = notice
                break
        return response

    # --- Prometheus Metrics ---
    if settings.prometheus_enabled:
        from prometheus_fastapi_instrumentator import Instrumentator

        Instrumentator().instrument(app).expose(app, endpoint="/metrics")

    # --- Routers ---
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["auth"])
    app.include_router(user_keys.router, prefix="/api/v1/user-keys", tags=["user-keys"])
    app.include_router(tenants.router, prefix="/api/v1/tenants", tags=["tenants"])
    app.include_router(cases.router, prefix="/api/v1", tags=["cases"])
    app.include_router(tags.router, prefix="/api/v1", tags=["tags"])
    app.include_router(projects.router, prefix="/api/v1/projects", tags=["projects"])
    app.include_router(debate.router, prefix="/api/v1/debate", tags=["debate"])
    app.include_router(debate_stream.router, prefix="/api/v1/debate", tags=["debate"])
    app.include_router(hitl_router, prefix="/api/v1/debate", tags=["hitl"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
    app.include_router(dms.router, prefix="/api/v1/dms", tags=["dms"])
    app.include_router(case_scoped_router, prefix="/api/v1", tags=["cases"])

    # --- Case-Space Workspace (Phase 1 of plans/2026-06-14_case-space-workspace.md) ---
    app.include_router(workspace.router, prefix="/api/v1", tags=["case-space"])
    app.include_router(inbox.router, prefix="/api/v1", tags=["case-space"])
    app.include_router(onboarding.router, prefix="/api/v1", tags=["case-space"])
    app.include_router(graph.router, prefix="/api/v1", tags=["case-space"])

    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])
    app.include_router(profiles.router, prefix="/api/v1/profiles", tags=["profiles"])

    # --- Module System ---
    app.include_router(modules.router, prefix="/api/v1/modules", tags=["modules"])

    # --- Translation ---
    app.include_router(translation_router, prefix="/api/v1/translation", tags=["translation"])
    app.include_router(ui_i18n_router, prefix="/api/v1/i18n", tags=["i18n"])

    app.include_router(health.router, prefix="/health", tags=["health"])
    app.include_router(system.router, prefix="/api/v1/system", tags=["system"])

    # --- LLM Activity Monitor ---
    app.include_router(monitor.router, prefix="/api/v1/monitor", tags=["monitor"])

    # --- Blueprint Canvas ---
    app.include_router(blueprints.router, prefix="/api/v1/blueprints", tags=["blueprints"])
    app.include_router(llm_profiles.router, prefix="/api/v1/blueprints/llm-profiles", tags=["blueprints"])
    app.include_router(argumentation_patterns.router, prefix="/api/v1/blueprints", tags=["blueprints"])
    app.include_router(workflow_definitions.router, prefix="/api/v1/blueprints/workflows", tags=["blueprints"])
    app.include_router(canvas.router, prefix="/api/v1/canvas", tags=["canvas"])
    app.include_router(
        blueprint_events.router,
        prefix="/api/v1/blueprint-events",
        tags=["blueprint-events"],
    )

    # --- Workflow Execution ---
    app.include_router(
        workflow_exec.router,
        prefix="/api/v1/workflow-exec",
        tags=["workflow-exec"],
    )

    # --- Workflow Reports ---
    app.include_router(
        workflow_reports.router,
        prefix="/api/v1",
        tags=["reports"],
    )

    # --- Workflow Templates ---
    app.include_router(
        workflow_templates.router,
        prefix="/api/v1/workflow-templates",
        tags=["workflow-templates"],
    )

    # --- Bundle Composer ---
    app.include_router(
        bundle_composer.router,
        prefix="/api/v1/bundle-composer",
        tags=["bundle-composer"],
    )

    # --- Tone Profiles ---
    app.include_router(
        tone_profiles.router,
        prefix="/api/v1/tone-profiles",
        tags=["tone-profiles"],
    )

    # --- A2A Discovery ---
    app.include_router(
        a2a_discovery.router,
        prefix="/api/v1/a2a",
        tags=["a2a-discovery"],
    )

    # --- Output Composer ---
    app.include_router(
        output_composer.router,
        prefix="/api/v1",
        tags=["output-composer"],
    )

    # --- Optimization Proposals (Reflection) ---
    app.include_router(
        optimization_proposals.router,
        prefix="/api/v1",
        tags=["optimization-proposals"],
    )

    # --- Input Composer ---
    app.include_router(
        input_composer.router,
        prefix="/api/v1",
        tags=["input-composer"],
    )

    # --- Danwa Assistant ---
    app.include_router(assistant.router)

    # --- Error handlers (Blueprint Canvas) ---
    from backend.api.errors import register_error_handlers

    register_error_handlers(app)

    # --- A2A Protocol (Agent-to-Agent) ---
    # Mounted at root so /.well-known/agent.json discovery works per A2A spec
    app.include_router(a2a_router, tags=["a2a"])

    # --- Static file serving (production mode) ---
    # Mount static assets first (more specific), then SPA fallback last
    if _FRONTEND_DIST.is_dir():
        # Serve built assets (JS, CSS, images)
        app.mount(
            "/assets",
            StaticFiles(directory=_FRONTEND_DIST / "assets"),
            name="static-assets",
        )

        # Serve favicon and other root-level static files
        app.mount(
            "/",
            StaticFiles(directory=_FRONTEND_DIST, html=True),
            name="frontend",
        )

    return app


# Uvicorn entry point
app = create_app()
