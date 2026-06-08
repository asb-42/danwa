"""Output Composer — API router for plugin listing, render job management.

Endpoints:
- GET  /api/v1/output-plugins                — list registered plugins
- POST /api/v1/sessions/{session_id}/render   — start a render job
- GET  /api/v1/render-jobs/{job_id}           — job status
- GET  /api/v1/render-jobs/{job_id}/download  — download generated file
- DELETE /api/v1/render-jobs/{job_id}          — delete job + files
"""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_debate_store_for_case, get_project_id
from backend.services.output.registry import PluginRegistry
from backend.services.render_engine import RenderEngineService
from backend.services.render_job_store import RenderJobStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["output-composer"])

# Module-level singletons
_engine: RenderEngineService | None = None
_job_store: RenderJobStore | None = None


def _get_engine() -> RenderEngineService:
    """Return (or lazily create) engine."""
    global _engine
    if _engine is None:
        # Ensure plugins are imported (triggers @register_plugin)
        import backend.services.output.plugins  # noqa: F401

        _engine = RenderEngineService()
    return _engine


def _get_job_store() -> RenderJobStore:
    """Return (or lazily create) job store."""
    global _job_store
    if _job_store is None:
        _job_store = RenderJobStore()
    return _job_store


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class PluginInfo(BaseModel):
    """Information about a registered output plugin."""

    plugin_key: str
    plugin_name: str
    supported_formats: list[str]
    config_schema: dict[str, Any] = Field(description="JSON Schema for the plugin's config, usable for dynamic form generation")


class CreateRenderRequest(BaseModel):
    """Request body for starting a render job."""

    plugin_key: str = Field(description="Key of the output plugin (e.g. 'print', 'tts')")
    config: dict = Field(default_factory=dict, description="Plugin-specific configuration")


class CreateRenderResponse(BaseModel):
    """Response after creating a render job."""

    job_id: str
    session_id: str
    plugin_key: str
    status: str = "queued"


class RenderJobStatusResponse(BaseModel):
    """Response for render job status query."""

    job_id: str
    session_id: str
    plugin_key: str
    status: str
    output_files: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    progress_current: int = 0
    progress_total: int = 0


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/output-plugins", response_model=list[PluginInfo])
async def list_output_plugins() -> list[PluginInfo]:
    """List all registered output plugins with their config schemas."""
    # Ensure plugins are imported (triggers @register_plugin)
    import backend.services.output.plugins  # noqa: F401

    registry = PluginRegistry.instance()
    plugins = registry.list_plugins()
    return [
        PluginInfo(
            plugin_key=p.plugin_key,
            plugin_name=p.plugin_name,
            supported_formats=list(p.supported_formats),
            config_schema=p.config_json_schema(),
        )
        for p in plugins
    ]


@router.post(
    "/sessions/{session_id}/render",
    response_model=CreateRenderResponse,
    status_code=202,
)
async def create_render_job(
    session_id: str,
    body: CreateRenderRequest,
) -> CreateRenderResponse:
    """Start a render job for a completed session.

    The job runs asynchronously.  Poll GET /api/v1/render-jobs/{job_id}
    for status updates.
    """
    engine = _get_engine()
    try:
        job = await engine.submit_job(
            session_id=session_id,
            plugin_key=body.plugin_key,
            config=body.config,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return CreateRenderResponse(
        job_id=job.id,
        session_id=job.session_id,
        plugin_key=job.plugin_key,
        status=job.status.value,
    )


@router.get("/render-jobs/{job_id}", response_model=RenderJobStatusResponse)
async def get_render_job_status(job_id: str) -> RenderJobStatusResponse:
    """Get the status and metadata of a render job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Render job {job_id!r} not found")

    return RenderJobStatusResponse(
        job_id=job.id,
        session_id=job.session_id,
        plugin_key=job.plugin_key,
        status=job.status.value,
        output_files=job.output_files,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        started_at=job.started_at.isoformat() if job.started_at else None,
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        progress_current=job.progress_current,
        progress_total=job.progress_total,
    )


@router.get("/render-jobs/{job_id}/download")
async def download_render_file(job_id: str, file_index: int = 0) -> FileResponse:
    """Download a generated output file.

    Args:
        job_id: The render job ID.
        file_index: Index of the file in output_files (default 0).
    """
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Render job {job_id!r} not found")

    if job.status.value != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed (status={job.status.value})",
        )

    if file_index < 0 or file_index >= len(job.output_files):
        raise HTTPException(
            status_code=400,
            detail=f"file_index {file_index} out of range (0..{len(job.output_files) - 1})",
        )

    file_path = Path(job.output_files[file_index])
    if not file_path.exists():
        raise HTTPException(status_code=410, detail="Output file no longer exists")

    # Determine Content-Type from extension
    content_type, _ = mimetypes.guess_type(str(file_path))
    if content_type is None:
        content_type = "application/octet-stream"

    # Generate user-friendly filename: {session_id}_{date}.{ext}
    ext = file_path.suffix
    date_str = job.created_at.strftime("%Y-%m-%d") if job.created_at else "unknown"
    friendly_name = f"{job.session_id[:12]}_{date_str}{ext}"
    return FileResponse(
        path=str(file_path),
        media_type=content_type,
        filename=friendly_name,
    )


@router.delete("/render-jobs/{job_id}", status_code=204)
async def delete_render_job(job_id: str) -> None:
    """Delete a render job and its output files.

    Performs a hard delete — removes the job record and optionally
    the output directory.
    """
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Render job {job_id!r} not found")

    # Delete output files
    for file_path_str in job.output_files:
        file_path = Path(file_path_str)
        if file_path.exists():
            file_path.unlink(missing_ok=True)

    # Delete job directory if empty
    if job.output_files:
        job_dir = Path(job.output_files[0]).parent
        if job_dir.exists() and not any(job_dir.iterdir()):
            job_dir.rmdir()

    # Delete job record
    store.delete_job(job_id)


# ---------------------------------------------------------------------------
# Session Agent Roles (for TTS voice mapping pre-fill)
# ---------------------------------------------------------------------------


@router.get("/render-sessions/{session_id}/agents")
async def get_session_agents(session_id: str) -> list[dict]:
    """Return unique agent roles from a completed session's artifact.

    Used by the frontend to pre-populate the TTS voice mapping editor.

    Returns:
        List of ``{"role_type": str, "agent_name": str}`` from the
        debate transcript.
    """
    artifact_store = _get_engine().artifact_store
    artifact = artifact_store.get(session_id)
    if not artifact:
        return []

    seen: set[tuple[str, str]] = set()
    agents: list[dict] = []
    for turn in artifact.transcript:
        key = (turn.role_type, turn.agent_name)
        if key not in seen:
            seen.add(key)
            agents.append({"role_type": turn.role_type, "agent_name": turn.agent_name})
    return agents


# ---------------------------------------------------------------------------
# TTS Voices
# ---------------------------------------------------------------------------


@router.get("/tts-voices")
async def list_tts_voices(
    language: str | None = None,
    gender: str | None = None,
    engine: str | None = None,
) -> list[dict]:
    """List available TTS voices with optional filters.

    Args:
        language: Filter by language prefix (e.g. "de", "en").
        gender: Filter by gender ("Male" / "Female").
        engine: If "mimo_tts", return MiMo voices instead of edge-tts voices.
    """
    if engine == "mimo_tts":
        from backend.services.output.plugins.mimo_tts_renderer import list_mimo_voices

        return list_mimo_voices(language=language, gender=gender)

    from backend.services.output.plugins.voice_store import VoiceStore

    store = VoiceStore()
    return store.list_voices(language=language, gender=gender)


# ---------------------------------------------------------------------------
# Session Search (for autocomplete)
# ---------------------------------------------------------------------------


@router.get("/render-sessions")
async def search_sessions(
    q: str = "",
    limit: int = 20,
    project_id: str = Depends(get_project_id),
) -> list[dict]:
    """Search completed sessions by ID or debate title for autocomplete.

    Returns sessions that have a saved DebateArtifact.
    """
    artifact_store = _get_engine().artifact_store
    debate_store = get_debate_store_for_case(project_id)
    results: list[dict] = []

    # Get all debates and filter by those with artifacts
    debates = debate_store.list_all(limit=200)
    for d in debates:
        did = d.get("debate_id", "")
        title = d.get("title", "")
        status = d.get("status", "")
        is_mvp = d.get("is_mvp", False)

        # Only completed sessions
        if status not in ("completed",):
            continue

        # For MVP debates: use the workflow session_id, skip artifact check
        # (MVP debates store state in workflow snapshots, not legacy DebateArtifacts)
        if is_mvp:
            session_id = d.get("session_id")
            if not session_id:
                continue
        else:
            # Legacy debates: check if artifact exists
            if not artifact_store.exists(did):
                continue
            session_id = did

        # Filter by query (match debate_id, title, or session_id)
        if q:
            q_lower = q.lower()
            sid = d.get("session_id", "") or ""
            if q_lower not in did.lower() and q_lower not in title.lower() and q_lower not in sid.lower():
                continue

        results.append(
            {
                "session_id": session_id,
                "title": title or did,
                "status": status,
            }
        )

        if len(results) >= limit:
            break

    return results
