"""API router for Document Management System (documents, RAG).

.. deprecated::
    These routes are deprecated. Use ``/api/v1/tenants/{tid}/cases/{cid}/dms/``
    instead. Legacy routes will be removed in a future version.
"""

import asyncio
import logging
import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.api.deps import get_case_dir, get_profile_service_for_case, get_project_id
from backend.services.dms.document_analyzer import (
    analyze_documents as run_document_analysis,
)
from backend.services.dms.document_analyzer import (
    load_analysis,
    save_analysis,
    update_analysis,
)
from backend.services.dms.service import get_dms_for_project

logger = logging.getLogger(__name__)

_DEPRECATION_NOTICE = "Use /api/v1/tenants/{tid}/cases/{cid}/dms/ instead. See /api/v1/dms for deprecation details."

router = APIRouter()


class MoveDocumentRequest(BaseModel):
    """MoveDocumentRequest class."""

    target_project_id: str


class UpdateDocumentTextRequest(BaseModel):
    """UpdateDocumentTextRequest class."""

    text: str


# --- Documents ---


@router.get("/documents")
def list_documents(
    project_id: str = Depends(get_project_id),
):
    """List documents in the active project."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return dms.list_documents(project_id)


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    project_id: str = Depends(get_project_id),
):
    """Get a single document with its content for viewing."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    doc = dms.get_document_content(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return doc


@router.put("/documents/{document_id}/text")
def update_document_text(
    document_id: str,
    body: UpdateDocumentTextRequest,
    project_id: str = Depends(get_project_id),
):
    """Update the extracted text of a document (re-chunks and re-indexes)."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    result = dms.update_document_text(document_id, body.text)
    if not result:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return result


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    project_id: str = Depends(get_project_id),
):
    """Upload a document to the active project."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Preserve original filename
    original_filename = file.filename or "upload.bin"

    # Save uploaded file to a temp location
    suffix = os.path.splitext(original_filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()

        # Check file size against DMS config limit
        from backend.services.dms.config import load_dms_config

        try:
            dms_config = load_dms_config()
            max_bytes = dms_config.get("max_file_size_mb", 50) * 1024 * 1024
        except Exception:
            max_bytes = 50 * 1024 * 1024  # 50 MB default

        if len(content) > max_bytes:
            os.unlink(tmp.name)
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({len(content)} bytes). Maximum allowed: {max_bytes // (1024 * 1024)} MB",
            )

        tmp.write(content)
        tmp_path = tmp.name

    try:
        result = dms.upload_document(project_id, tmp_path, original_filename=original_filename)
        doc_id = result.get("doc_id", "")
        if not doc_id:
            raise HTTPException(status_code=500, detail="Failed to upload document")
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        return {
            "status": "ok",
            "document_id": doc_id,
            "filename": original_filename,
            "chunk_count": result.get("chunk_count", 0),
            "ocr_used": result.get("ocr_used", False),
            "ocr_engine": result.get("ocr_engine"),
            "char_count": result.get("char_count", 0),
            "word_count": result.get("word_count", 0),
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError as e:
            logger.debug("Failed to clean up temp file %s: %s", tmp_path, e)


@router.delete("/documents/{document_id}")
def delete_document(
    document_id: str,
    project_id: str = Depends(get_project_id),
):
    """Delete a document from the active project."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    result = dms.delete_document(document_id)
    if result:
        return {"status": "ok", "deleted": document_id}
    raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


@router.post("/documents/{document_id}/move")
def move_document(
    document_id: str,
    body: MoveDocumentRequest,
    project_id: str = Depends(get_project_id),
):
    """Move a document to another project.

    Source project is determined by the ``X-Project-Id`` header.
    The document is removed from the source project's DMS and
    re-created in the target project's DMS (with a new document ID).
    """
    if body.target_project_id == project_id:
        raise HTTPException(status_code=400, detail="Source and target project are the same")

    try:
        src_dms = get_dms_for_project(project_id)
        tgt_dms = get_dms_for_project(body.target_project_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    success = src_dms.move_document_to(document_id, tgt_dms, body.target_project_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found or move failed")

    return {"status": "ok", "moved": document_id, "target_project_id": body.target_project_id}


# --- RAG Context ---


@router.post("/documents/{document_id}/rag")
def add_to_rag(
    document_id: str,
    project_id: str = Depends(get_project_id),
):
    """Add a document to manual RAG context.

    Returns 404 if the document does not belong to the active project.
    This prevents a caller from injecting a foreign document_id into the
    active project's manual RAG selection set.
    """
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    if dms.get_document(document_id) is None:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found in this project")
    result = dms.add_to_rag_context(document_id)
    if result:
        return {"status": "ok", "added": document_id}
    raise HTTPException(status_code=400, detail="Document already in RAG context")


@router.delete("/documents/{document_id}/rag")
def remove_from_rag(
    document_id: str,
    project_id: str = Depends(get_project_id),
):
    """Remove a document from manual RAG context."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    result = dms.remove_from_rag_context(document_id)
    if result:
        return {"status": "ok", "removed": document_id}
    raise HTTPException(status_code=400, detail="Document not in RAG context")


@router.get("/rag/manual")
def list_manual_rag(
    project_id: str = Depends(get_project_id),
):
    """List document IDs in manual RAG context."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"document_ids": dms.list_manual_rag_documents()}


@router.get("/rag/search")
def search_rag(
    query: str,
    k: int = 5,
    project_id: str = Depends(get_project_id),
):
    """Search RAG context for relevant chunks."""
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    results = dms.get_rag_context(query, project_id=project_id, k=k)
    return {"results": results}


# --- OCR Status ---


@router.get("/ocr-status")
def ocr_status():
    """Check which OCR engines are available for image text extraction.

    Returns:
        Dict with ``available`` (bool) and ``engine`` (str or null)
        indicating the available OCR engine ("paddleocr", "easyocr",
        "tesseract", or null).
    """
    # Try PaddleOCR first
    try:
        import paddleocr  # noqa: F401

        return {"available": True, "engine": "paddleocr"}
    except ImportError:
        pass
    except (RuntimeError, AssertionError) as e:
        if "PDX has already been initialized" in str(e) or "paddle is unexpectedly loaded" in str(e):
            logger.warning("PaddleX/PaddleOCR initialization conflict - OCR may still be available: %s", e)
            return {"available": True, "engine": "paddleocr"}
        # Fall through to next check

    # Try EasyOCR
    try:
        import easyocr  # noqa: F401

        return {"available": True, "engine": "easyocr"}
    except ImportError:
        pass
    except Exception as e:
        logger.debug("EasyOCR check failed: %s", e)

    # Fallback: Try tesseract
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return {"available": True, "engine": "tesseract"}
    except Exception as e:
        logger.debug("Tesseract check failed: %s", e)

    return {"available": False, "engine": None}


@router.post("/analyze")
async def analyze_documents(
    language: str = Query("de", description="Language for analysis content (e.g. 'de', 'en')"),
    mode: str = Query("full", description="Analysis mode: 'full' (regenerate all) or 'update' (merge new docs only)"),
    project_id: str = Depends(get_project_id),
):
    """Analyze documents in the project and produce a structured case analysis.

    Uses the utility LLM to summarize, extract key facts, parties,
    timeline, and issues from all uploaded documents.

    Two modes:
    - ``full`` (default): Re-analyze all documents from scratch.
    - ``update``: Merge new documents into an existing analysis without
      re-processing already analyzed documents.
    """
    try:
        dms = get_dms_for_project(project_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = dms.list_documents(project_id)
    if not documents:
        raise HTTPException(status_code=400, detail="No documents to analyze")

    profile_service = get_profile_service_for_case(project_id)
    project_dir = get_case_dir(project_id)

    if mode == "update":
        existing = load_analysis(project_dir)
        if not existing:
            raise HTTPException(
                status_code=400,
                detail="No existing analysis found. Run full analysis first.",
            )

        known_filenames = {d.get("filename", "") for d in existing.get("documents", [])}
        new_documents = [d for d in documents if d.get("filename", "") not in known_filenames]

        if not new_documents:
            return {"status": "ok", "message": "No new documents to analyze", "analysis": existing}

        document_texts = []
        for doc in new_documents:
            content = dms.get_document_content(doc["id"])
            text = (content or {}).get("text_content", "")
            if text:
                document_texts.append({"filename": doc.get("filename", "unknown"), "text": text})

        if not document_texts:
            return {"status": "ok", "message": "No extractable text in new documents", "analysis": existing}

        analysis = await asyncio.to_thread(update_analysis, existing, document_texts, profile_service=profile_service, language=language)
        if "error" in analysis:
            raise HTTPException(status_code=500, detail=analysis["error"])

        try:
            save_analysis(project_dir, analysis)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Failed to save analysis: {e}")
        return {"status": "ok", "mode": "update", "analysis": analysis}

    # full mode
    document_texts = []
    for doc in documents:
        content = dms.get_document_content(doc["id"])
        text = (content or {}).get("text_content", "")
        if text:
            document_texts.append({"filename": doc.get("filename", "unknown"), "text": text})

    if not document_texts:
        raise HTTPException(status_code=400, detail="No extractable text found in documents")

    analysis = await asyncio.to_thread(run_document_analysis, document_texts, profile_service=profile_service, language=language)
    if "error" in analysis:
        raise HTTPException(status_code=500, detail=analysis["error"])

    try:
        save_analysis(project_dir, analysis)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Failed to save analysis: {e}")

    return {"status": "ok", "mode": "full", "analysis": analysis}


@router.get("/analyze")
def get_analysis(
    project_id: str = Depends(get_project_id),
):
    """Get the stored document analysis for the current project."""
    from backend.api.deps import get_project_store

    project = get_project_store().get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_case_dir(project_id)
    analysis = load_analysis(project_dir)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

    return {"status": "ok", "analysis": analysis}


# ---------------------------------------------------------------------------
# Analysis Export
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent.parent / "templates" / "print"


class AnalysisExportRequest(BaseModel):
    """AnalysisExportRequest class."""

    format: str = "pdf"


@router.post("/analyze/export")
async def export_analysis(
    body: AnalysisExportRequest,
    project_id: str = Depends(get_project_id),
):
    """Export the document analysis as PDF, ODT, or Markdown."""
    from backend.api.deps import get_project_store

    project = get_project_store().get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = get_case_dir(project_id)
    project_name = getattr(project, "name", project_id)

    analysis = load_analysis(project_dir)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

    fmt = body.format.lower()
    if fmt not in ("pdf", "odt", "md"):
        raise HTTPException(status_code=422, detail=f"Unsupported format: {fmt}")

    # Render HTML
    from datetime import UTC, datetime

    import jinja2

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
    )
    template = env.get_template("document_analysis.html")
    now = datetime.now(UTC)
    i18n = _load_analysis_i18n("de")
    html = template.render(
        project_name=project_name,
        analysis=analysis,
        language="de",
        generated=now.strftime("%Y-%m-%d %H:%M UTC"),
        i18n=i18n,
    )

    # Generate output file
    import tempfile as _tf

    stem = f"analysis_{project_id[:8]}_{now.strftime('%Y%m%d_%H%M')}"

    if fmt == "pdf":
        from weasyprint import HTML

        tmp = _tf.NamedTemporaryFile(suffix=".pdf", delete=False)
        HTML(string=html).write_pdf(tmp.name)
        media_type = "application/pdf"
        filename = f"{stem}.pdf"

    elif fmt == "odt":
        tmp = _tf.NamedTemporaryFile(suffix=".odt", delete=False)
        try:
            import pypandoc

            pypandoc.convert_text(html, "odt", format="html", outputfile=tmp.name)
        except ImportError:
            tmp.write(html.encode("utf-8"))
        media_type = "application/vnd.oasis.opendocument.text"
        filename = f"{stem}.odt"

    elif fmt == "md":
        from backend.services.output.html_to_md import html_to_markdown

        md = html_to_markdown(html)
        tmp = _tf.NamedTemporaryFile(suffix=".md", delete=False)
        tmp.write(md.encode("utf-8"))
        media_type = "text/markdown"
        filename = f"{stem}.md"

    tmp.close()
    return FileResponse(tmp.name, media_type=media_type, filename=filename)


def _load_analysis_i18n(language: str) -> dict:
    """Load i18n labels for the document analysis template."""
    labels = {
        "case_summary_label": ("Fallzusammenfassung" if language == "de" else "Case Summary"),
        "key_facts_label": ("Wichtige Fakten" if language == "de" else "Key Facts"),
        "parties_label": ("Parteien" if language == "de" else "Parties"),
        "timeline_label": ("Zeitstrahl" if language == "de" else "Timeline"),
        "key_issues_label": ("Hauptstreitpunkte" if language == "de" else "Key Issues"),
        "documents_label": ("Dokumentübersichten" if language == "de" else "Document Summaries"),
    }
    return labels
