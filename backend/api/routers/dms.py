"""API router for Document Management System (documents, RAG)."""

import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.api.deps import get_project_id, get_project_store
from backend.services.dms.service import get_dms_for_project

logger = logging.getLogger(__name__)

router = APIRouter()


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
        }
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


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
    """Check whether PaddleOCR is available for image text extraction.

    Returns:
        Dict with ``available`` (bool) and ``engine`` (str or null).
    """
    try:
        import paddleocr  # noqa: F401

        return {"available": True, "engine": "paddleocr"}
    except ImportError:
        return {"available": False, "engine": None}
    except (RuntimeError, AssertionError) as e:
        if "PDX has already been initialized" in str(e) or "paddle is unexpectedly loaded" in str(e):
            logger.warning("PaddleX/PaddleOCR initialization conflict - OCR may still be available: %s", e)
            return {"available": True, "engine": "paddleocr"}
        return {"available": False, "engine": None, "error": str(e)}
