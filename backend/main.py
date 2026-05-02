"""FastAPI application entry point for Debate Engine v2.0."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api.deps import get_settings
from backend.api.routers import audit, debate, config, dms, health, sessions

# Path to built frontend assets (relative to project root)
_FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    settings = get_settings()
    # Ensure DB directory exists
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    yield


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        lifespan=lifespan,
    )

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Routers ---
    app.include_router(debate.router, prefix="/api/v1/debate", tags=["debate"])
    app.include_router(audit.router, prefix="/api/v1/audit", tags=["audit"])
    app.include_router(config.router, prefix="/api/v1/config", tags=["config"])
    app.include_router(dms.router, prefix="/api/v1/dms", tags=["dms"])
    app.include_router(sessions.router, prefix="/api/v1/sessions", tags=["sessions"])

    app.include_router(health.router, prefix="/health", tags=["system"])

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
