"""FastAPI application entry point for Debate Engine v2.0."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from debate_engine.api.deps import get_settings
from debate_engine.api.routers import debate
from debate_engine.models.schemas import HealthResponse

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

    # --- Health check ---
    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(status="ok", version=settings.app_version)

    # --- Static file serving (production mode) ---
    if _FRONTEND_DIST.is_dir():
        # Serve built assets (JS, CSS, images)
        app.mount("/assets", StaticFiles(directory=_FRONTEND_DIST / "assets"), name="static-assets")

        # SPA fallback — serve index.html for all non-API routes
        @app.get("/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
        async def spa_fallback(request: Request, full_path: str) -> FileResponse:
            """Serve index.html for SPA client-side routing."""
            # Check if the requested file exists in dist
            file_path = _FRONTEND_DIST / full_path
            if file_path.is_file():
                return FileResponse(file_path)
            # Otherwise serve index.html for SPA routing
            return FileResponse(_FRONTEND_DIST / "index.html")

    return app


# Uvicorn entry point
app = create_app()
