"""System management API router.

Provides endpoints for profile reloading and log viewing.
"""

from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

_LOG_DIR = Path(__file__).resolve().parent.parent.parent.parent / "logs"
_LOG_FILE = _LOG_DIR / "debate-agent.log"


@router.post("/reload-profiles")
def reload_profiles() -> dict:
    """Reload all profiles from YAML files.

    Forces ProfileService and PromptService singletons to re-read
    their YAML/markdown files from disk. Also clears the workflow
    nodes' cached ProfileService instances so running debates pick
    up the updated profiles immediately.
    """
    from backend.api.routers.profiles import get_profile_service
    from backend.workflow import legacy_nodes as workflow_nodes
    from backend.workflow import node_functions

    try:
        ps = get_profile_service()
        ps.reload()
        logger.info("Profiles reloaded successfully")

        # Also clear prompt cache
        prompt_svc = workflow_nodes._get_prompt_service()
        prompt_svc.clear_cache()
        logger.info("Prompt cache cleared")

        # Clear workflow nodes' cached ProfileService/PromptService instances
        # so that running debates pick up updated profiles immediately
        workflow_nodes._profile_service_cache.clear()
        workflow_nodes._prompt_service_cache.clear()
        workflow_nodes._profile_service = None
        workflow_nodes._prompt_service = None
        node_functions._profile_service = None
        node_functions._prompt_service = None
        logger.info("Workflow nodes' profile/prompt service caches cleared")

        return {
            "status": "ok",
            "message": "Profiles and prompts reloaded",
            "llm_profiles": len(ps.list_llm_profiles()),
        }
    except Exception as exc:
        logger.error("Profile reload failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Reload failed: {exc}") from exc


@router.get("/logs")
def get_logs(
    lines: int = Query(default=100, ge=1, le=5000, description="Number of recent log lines"),
    search: str | None = Query(default=None, description="Filter lines containing this text"),
) -> dict:
    """Return recent backend log lines.

    Reads the last N lines from the log file, optionally filtered by a search term.
    """
    if not _LOG_FILE.exists():
        return {"lines": [], "total_lines": 0, "log_file": str(_LOG_FILE)}

    try:
        with open(_LOG_FILE, encoding="utf-8") as f:
            all_lines = f.readlines()

        if search:
            all_lines = [line for line in all_lines if search.lower() in line.lower()]

        # Return last N lines
        selected = all_lines[-lines:]
        return {
            "lines": [line.rstrip("\n") for line in selected],
            "total_lines": len(all_lines),
            "returned_lines": len(selected),
            "log_file": str(_LOG_FILE),
        }
    except Exception as exc:
        logger.error("Failed to read log file: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {exc}") from exc
