"""Workflow Reports — API router for async report generation.

Endpoints:
- POST /api/v1/sessions/{id}/report — create async report job
- GET  /api/v1/reports/{job_id}/status — query job status
- GET  /api/v1/reports/{job_id}/download — download generated report
- GET  /api/v1/sessions/{id}/report/stream — SSE progress stream
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_debate_store_for_case, get_project_id
from backend.api.events import publish_async, subscribe, unsubscribe
from backend.workflow.report_generator import WorkflowReportGenerator
from backend.workflow.report_jobs import ReportJobStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reports"])

# Module-level singletons
_job_store: ReportJobStore | None = None
_report_gen: WorkflowReportGenerator | None = None


def _get_job_store() -> ReportJobStore:
    """Return (or lazily create) job store."""
    global _job_store
    if _job_store is None:
        _job_store = ReportJobStore()
    return _job_store


def _get_report_gen() -> WorkflowReportGenerator:
    """Return (or lazily create) report gen."""
    global _report_gen
    if _report_gen is None:
        _report_gen = WorkflowReportGenerator()
    return _report_gen


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateReportRequest(BaseModel):
    """Request body for creating a report job."""

    format: str = Field(
        default="docx",
        description="Output format: 'docx', 'pdf', or 'odf'",
    )


class CreateReportResponse(BaseModel):
    """Response after creating a report job."""

    job_id: str
    status: str = "pending"
    format: str


class ReportStatusResponse(BaseModel):
    """Response for report job status query."""

    job_id: str
    session_id: str
    format: str
    status: str
    file_path: str | None = None
    error: str | None = None
    created_at: str
    completed_at: str | None = None


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _generate_report_job(
    job_id: str,
    session_id: str,
    fmt: str,
    project_id: str | None = None,
) -> None:
    """Background task that generates a report and updates the job store."""
    store = _get_job_store()
    gen = _get_report_gen()

    store.update_job(job_id, status="running")
    await publish_async(
        session_id,
        "report.progress",
        {
            "job_id": job_id,
            "status": "running",
            "progress": 50,
        },
    )

    try:
        # Load debate data from the project-scoped store
        debate_data = None
        if project_id:
            try:
                debate_store = get_debate_store_for_case(project_id)
                debate_data = debate_store.get(session_id)
            except Exception as exc:
                logger.warning(
                    "Could not load debate data for session %s (project %s): %s",
                    session_id,
                    project_id,
                    exc,
                )

        path = await gen.generate(session_id, fmt, debate_data=debate_data)
        store.update_job(job_id, status="completed", file_path=str(path))
        await publish_async(
            session_id,
            "report.progress",
            {
                "job_id": job_id,
                "status": "completed",
                "progress": 100,
            },
        )
    except Exception as exc:
        logger.error("Report generation failed for job %s: %s", job_id, exc, exc_info=True)
        store.update_job(job_id, status="failed", error=str(exc))
        await publish_async(
            session_id,
            "report.progress",
            {
                "job_id": job_id,
                "status": "failed",
                "error": str(exc),
            },
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/sessions/{session_id}/report", response_model=CreateReportResponse)
async def create_report_job(
    session_id: str,
    body: CreateReportRequest,
    background_tasks: BackgroundTasks,
    project_id: str = Depends(get_project_id),
) -> CreateReportResponse:
    """Create an async report generation job.

    Returns immediately with a ``job_id``.  The report is generated in the
    background and can be downloaded via ``GET /api/v1/reports/{job_id}/download``
    once the status is ``"completed"``.
    """
    fmt = body.format
    if fmt not in ("docx", "pdf", "odf"):
        raise HTTPException(
            status_code=422,
            detail="Format must be 'docx', 'pdf', or 'odf'",
        )

    store = _get_job_store()
    job_id = store.create_job(session_id, fmt)

    background_tasks.add_task(_generate_report_job, job_id, session_id, fmt, project_id)

    return CreateReportResponse(job_id=job_id, status="pending", format=fmt)


@router.get("/reports/{job_id}/status", response_model=ReportStatusResponse)
async def get_report_status(job_id: str) -> ReportStatusResponse:
    """Get the status of a report generation job."""
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found")

    return ReportStatusResponse(
        job_id=job["id"],
        session_id=job["session_id"],
        format=job["format"],
        status=job["status"],
        file_path=job.get("file_path"),
        error=job.get("error"),
        created_at=job["created_at"],
        completed_at=job.get("completed_at"),
    )


@router.get("/reports/{job_id}/download")
async def download_report(job_id: str):
    """Download a completed report file.

    Returns a ``FileResponse`` with the appropriate media type.
    Raises 404 if the job is not found or not yet completed.
    """
    store = _get_job_store()
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Report job '{job_id}' not found")
    if job["status"] != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Report job is '{job['status']}', not 'completed'",
        )
    if not job.get("file_path"):
        raise HTTPException(status_code=500, detail="Report file path missing")

    path = Path(job["file_path"])
    if not path.exists():
        raise HTTPException(status_code=404, detail="Report file not found on disk")

    fmt = job["format"]
    media_types = {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "pdf": "application/pdf",
        "odf": "application/vnd.oasis.opendocument.text",
    }
    return FileResponse(
        path=str(path),
        media_type=media_types.get(fmt, "application/octet-stream"),
        filename=path.name,
    )


@router.get("/sessions/{session_id}/report/stream")
async def stream_report_progress(session_id: str):
    """SSE endpoint for real-time report generation progress.

    Yields ``report.progress`` events for all report jobs belonging to
    the given session.
    """
    from sse_starlette.sse import EventSourceResponse

    async def event_generator():
        """Event generator the instance."""
        queue = subscribe(session_id)
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    if event.get("type") == "report.progress":
                        yield {
                            "event": "report.progress",
                            "data": str(event.get("data", "")),
                        }
                except TimeoutError:
                    yield {"event": "ping", "data": ""}
        finally:
            unsubscribe(session_id, queue)

    return EventSourceResponse(event_generator())
