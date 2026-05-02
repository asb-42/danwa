"""FastAPI main application — serves the SPA and mounts API routers."""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.server.routers import config, dms, sessions, debate

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Debate-Agent",
    description="Multi-agent debate system with configurable agents",
    version="0.2.0",
)

# --- API routers ---
app.include_router(debate.router, prefix="/api/debate", tags=["debate"])
app.include_router(config.router, prefix="/api/config", tags=["config"])
app.include_router(dms.router, prefix="/api/dms", tags=["dms"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])

# --- Static files ---
STATIC_DIR = Path("static")
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", response_class=None)
async def root():
    """Serve the SPA entry point."""
    index = STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return {"message": "Debate-Agent API is running. Frontend not built yet."}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.server.main:app", host="0.0.0.0", port=7860, reload=True)
