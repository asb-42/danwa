"""Input Composer API — endpoints for input plugin listing, submission, and job management.

Endpoints:
- GET  /api/v1/input-plugins                 — list input plugins
- POST /api/v1/input/submit                  — submit input
- GET  /api/v1/input/jobs/{job_id}           — job status
- DELETE /api/v1/input/jobs/{job_id}         — delete job
- POST /api/v1/input/a2a/{task_id}/approve   — approve A2A request
- POST /api/v1/input/a2a/{task_id}/reject    — reject A2A request
- POST /api/v1/mcp/tools/call                — reserved for future MCP
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.input.input_engine import InputComposerService
from backend.services.input.input_job_store import InputJobStore
from backend.services.input.registry import InputPluginRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["input-composer"])

# Module-level singletons
_engine: InputComposerService | None = None
_job_store: InputJobStore | None = None


def _get_engine() -> InputComposerService:
    global _engine
    if _engine is None:
        # Ensure plugins are imported (triggers @register_input_plugin)
        import backend.services.input.plugins  # noqa: F401
        _engine = InputComposerService()
    return _engine


def _get_job_store() -> InputJobStore:
    global _job_store
    if _job_store is None:
        _job_store = InputJobStore()
    return _job_store


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class InputPluginInfo(BaseModel):
    """Information about a registered input plugin."""

    plugin_key: str
    plugin_name: str
    config_schema: dict[str, Any] = Field(
        description="JSON Schema for the plugin's config"
    )
    ui_hints: dict[str, Any] = Field(
        default_factory=dict,
        description="Frontend metadata (requires_microphone, supports_streaming, etc.)"
    )


class SubmitInputRequest(BaseModel):
    """Request body for submitting input."""

    plugin_key: str = Field(
        default="standard_text",
        description="Key of the input plugin to use",
    )
    config: dict = Field(
        default_factory=dict,
        description="Plugin-specific configuration",
    )
    topic: str = Field(
        default="",
        description="The debate topic / case description",
    )
    raw_data: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional raw input data",
    )


class SubmitInputResponse(BaseModel):
    """Response after submitting input."""

    job_id: str
    plugin_key: str
    status: str


class InputJobStatusResponse(BaseModel):
    """Response for input job status query."""

    job_id: str
    plugin_key: str
    status: str
    processed_input: dict[str, Any] | None = None
    error_message: str | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/input-plugins", response_model=list[InputPluginInfo])
async def list_input_plugins() -> list[InputPluginInfo]:
    """List all registered input plugins with their config schemas and UI hints."""
    registry = InputPluginRegistry.instance()
    plugins = registry.list_plugins()
    result: list[InputPluginInfo] = []
    for p in plugins:
        try:
            instance = p()
            hints = instance.get_ui_hints()
        except Exception:
            hints = {}
        result.append(
            InputPluginInfo(
                plugin_key=p.plugin_key,
                plugin_name=p.plugin_name,
                config_schema=p.config_json_schema(),
                ui_hints=hints,
            )
        )
    return result


@router.post("/input/submit", response_model=SubmitInputResponse, status_code=202)
async def submit_input(body: SubmitInputRequest) -> SubmitInputResponse:
    """Submit input for processing by an Input Plugin."""
    engine = _get_engine()

    # Merge topic into raw_data
    raw_data = {**body.raw_data}
    if body.topic:
        raw_data["topic"] = body.topic

    try:
        job = await engine.submit_input(
            plugin_key=body.plugin_key,
            config=body.config,
            raw_data=raw_data,
        )
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    return SubmitInputResponse(
        job_id=job.id,
        plugin_key=job.plugin_key,
        status=job.status.value,
    )


@router.get("/input/jobs/{job_id}", response_model=InputJobStatusResponse)
async def get_input_job_status(job_id: str) -> InputJobStatusResponse:
    """Get the status and metadata of an input job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Input job {job_id!r} not found")

    processed = None
    if job.processed_input:
        processed = job.processed_input.model_dump(mode="json")

    return InputJobStatusResponse(
        job_id=job.id,
        plugin_key=job.plugin_key,
        status=job.status.value,
        processed_input=processed,
        error_message=job.error_message,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
    )


@router.delete("/input/jobs/{job_id}", status_code=204)
async def delete_input_job(job_id: str) -> None:
    """Delete an input job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Input job {job_id!r} not found")
    store.delete_job(job_id)


@router.post("/input/a2a/{task_id}/approve")
async def approve_a2a(task_id: str) -> dict:
    """Approve a pending A2A inbound request."""
    engine = _get_engine()
    try:
        job = await engine.approve_a2a(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {task_id!r} not found")
    return {"job_id": job.id, "status": job.status.value}


@router.post("/input/a2a/{task_id}/reject")
async def reject_a2a(task_id: str) -> dict:
    """Reject a pending A2A inbound request."""
    engine = _get_engine()
    try:
        job = await engine.reject_a2a(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {task_id!r} not found")
    return {"job_id": job.id, "status": job.status.value}


@router.post("/mcp/tools/call")
async def mcp_tools_call() -> dict:
    """Reserved endpoint for future MCP server integration.

    Currently returns 501 Not Implemented.
    """
    raise HTTPException(
        status_code=501,
        detail="MCP tools/call is not yet implemented. This is a reserved endpoint.",
    )
