"""API router for debate session history (list, delete, export reports, traces)."""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from src.core.debate_engine import DebateState
from src.core.session_db import SessionDB
from src.core.trace_logger import TraceLogger
from src.tools.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-init singletons
_db: SessionDB | None = None
_report_gen: ReportGenerator | None = None


def get_db() -> SessionDB:
    """Retrieve and return db."""
    global _db
    if _db is None:
        _db = SessionDB()
    return _db


def get_report_gen() -> ReportGenerator:
    """Retrieve and return report gen."""
    global _report_gen
    if _report_gen is None:
        _report_gen = ReportGenerator()
    return _report_gen


@router.get("")
def list_sessions(
    limit: int = 20,
    offset: int = 0,
    min_consensus: float | None = None,
    project_id: str | None = None,
):
    """List past debate sessions."""
    db = get_db()
    sessions = db.list_sessions(limit=limit, offset=offset, min_consensus=min_consensus, project_id=project_id)
    return {"sessions": sessions}


@router.get("/{session_id}")
def get_session(session_id: str):
    """Get a single session by ID."""
    db = get_db()
    session = db.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return session


@router.delete("/{session_id}")
def delete_session(session_id: str):
    """Delete a session."""
    db = get_db()
    db.delete_session(session_id)
    return {"status": "ok", "deleted": session_id}


@router.get("/{session_id}/trace")
def get_trace(session_id: str):
    """Get the audit trace for a session."""
    logger_instance = TraceLogger(session_id)
    log = logger_instance.get_session_log()
    if not log:
        raise HTTPException(status_code=404, detail=f"No trace found for session '{session_id}'")
    return {"session_id": session_id, "entries": log}


@router.get("/{session_id}/report/{fmt}")
async def download_report(session_id: str, fmt: str):
    """Generate and download a report (docx or pdf) for a session."""
    if fmt not in ("docx", "pdf"):
        raise HTTPException(status_code=400, detail="Format must be 'docx' or 'pdf'")

    db = get_db()
    session = db.load_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    # Reconstruct a minimal DebateState for report generation
    trace_logger = TraceLogger(session_id)
    trace_log = trace_logger.get_session_log()

    state = DebateState(
        session_id=session_id,
        context=session.get("context_preview", ""),
        rounds=[],
        final_consensus=session.get("consensus", 0.0),
        output="",
        validation_report=[],
    )
    # Try to reconstruct output from trace
    if trace_log:
        last_entries = [e for e in trace_log if e.get("agent") not in ("search_validation",)]
        if last_entries:
            state.output = last_entries[-1].get("response_full", "")

    report_gen = get_report_gen()
    try:
        path = await report_gen.generate(state, fmt=fmt)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document" if fmt == "docx" else "application/pdf"
        return FileResponse(
            path=str(path),
            media_type=media_type,
            filename=f"debate_{session_id}.{fmt}",
        )
    except Exception as e:
        logger.error("Failed to generate report: %s", e)
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")
