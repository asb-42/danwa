"""API router for Document Management System (documents, RAG)."""

import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from backend.api.deps import get_profile_service_for_project, get_project_id, get_project_store
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

router = APIRouter()


class MoveDocumentRequest(BaseModel):
    target_project_id: str


class UpdateDocumentTextRequest(BaseModel):
    text: str


# --- Documents ---


@router.get("/documents")
def list_documents(
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """List documents in the active project."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return dms.list_documents(project_id)


@router.get("/documents/{document_id}")
def get_document(
    document_id: str,
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """Get a single document with its content for viewing."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
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
    project_store=Depends(get_project_store),
):
    """Update the extracted text of a document (re-chunks and re-indexes)."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
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
    project_store=Depends(get_project_store),
):
    """Upload a document to the active project."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    # Preserve original filename
    original_filename = file.filename or "upload.bin"

    # Save uploaded file to a temp location
    suffix = os.path.splitext(original_filename)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
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
    project_store=Depends(get_project_store),
):
    """Delete a document from the active project."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
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
    project_store=Depends(get_project_store),
):
    """Move a document to another project.

    Source project is determined by the ``X-Project-Id`` header.
    The document is removed from the source project's DMS and
    re-created in the target project's DMS (with a new document ID).
    """
    if body.target_project_id == project_id:
        raise HTTPException(status_code=400, detail="Source and target project are the same")

    try:
        src_dms = get_dms_for_project(project_id, project_store=project_store)
        tgt_dms = get_dms_for_project(body.target_project_id, project_store=project_store)
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
    project_store=Depends(get_project_store),
):
    """Add a document to manual RAG context."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    result = dms.add_to_rag_context(document_id)
    if result:
        return {"status": "ok", "added": document_id}
    raise HTTPException(status_code=400, detail="Document already in RAG context or not found")


@router.delete("/documents/{document_id}/rag")
def remove_from_rag(
    document_id: str,
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """Remove a document from manual RAG context."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    result = dms.remove_from_rag_context(document_id)
    if result:
        return {"status": "ok", "removed": document_id}
    raise HTTPException(status_code=400, detail="Document not in RAG context")


@router.get("/rag/manual")
def list_manual_rag(
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """List document IDs in manual RAG context."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"document_ids": dms.list_manual_rag_documents()}


@router.get("/rag/search")
def search_rag(
    query: str,
    k: int = 5,
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """Search RAG context for relevant chunks."""
    try:
        dms = get_dms_for_project(project_id, project_store=project_store)
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
        indicating the available OCR engine ("paddleocr" or "tesseract").
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
        # Fall through to tesseract check

    # Fallback: Try tesseract
    try:
        import pytesseract

        pytesseract.get_tesseract_version()
        return {"available": True, "engine": "tesseract"}
    except Exception as e:
        logger.debug("Tesseract check failed: %s", e)

    return {"available": False, "engine": None}


@router.post("/analyze")
def analyze_documents(
    language: str = Query("de", description="Language for analysis content (e.g. 'de', 'en')"),
    mode: str = Query("full", description="Analysis mode: 'full' (regenerate all) or 'update' (merge new docs only)"),
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
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
        dms = get_dms_for_project(project_id, project_store=project_store)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found")

    documents = dms.list_documents(project_id)
    if not documents:
        raise HTTPException(status_code=400, detail="No documents to analyze")

    profile_service = get_profile_service_for_project(project_id, project_store)
    project_dir = project_store.get_project_dir(project_id)

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

        analysis = update_analysis(existing, document_texts, profile_service=profile_service, language=language)
        if "error" in analysis:
            raise HTTPException(status_code=500, detail=analysis["error"])

        save_analysis(project_dir, analysis)
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

    analysis = run_document_analysis(document_texts, profile_service=profile_service, language=language)
    if "error" in analysis:
        raise HTTPException(status_code=500, detail=analysis["error"])

    save_analysis(project_dir, analysis)

    return {"status": "ok", "mode": "full", "analysis": analysis}


@router.get("/analyze")
def get_analysis(
    project_id: str = Depends(get_project_id),
    project_store=Depends(get_project_store),
):
    """Get the stored document analysis for the current project."""
    project = project_store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = project_store.get_project_dir(project_id)
    analysis = load_analysis(project_dir)
    if not analysis:
        raise HTTPException(status_code=404, detail="No analysis found. Run analysis first.")

    return {"status": "ok", "analysis": analysis}
