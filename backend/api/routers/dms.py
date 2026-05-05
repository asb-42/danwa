"""API router for Document Management System (projects, documents, RAG)."""

import logging
import os
import tempfile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from backend.api.deps import get_project_id, get_project_store
from src.dms.dms import DMS

logger = logging.getLogger(__name__)

router = APIRouter()

# Cache DMS instances per project directory
_dms_cache: dict[str, DMS] = {}


def _get_dms_for_project(project_id: str) -> DMS:
    """Get or create a DMS instance for a specific project."""
    if project_id in _dms_cache:
        return _dms_cache[project_id]

    store = get_project_store()
    project = store.get(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    project_dir = store.get_project_dir(project_id)
    dms_dir = project_dir / "dms"
    dms_dir.mkdir(parents=True, exist_ok=True)

    dms = DMS(db_path=str(dms_dir / "dms.db"), chroma_path=str(dms_dir / "chroma_db"))
    _dms_cache[project_id] = dms
    return dms


class ProjectBody(BaseModel):
    name: str
    description: str = ""


# --- Documents ---


@router.get("/documents")
def list_documents(
    project_id: str = Depends(get_project_id),
):
    """List documents in the active project."""
    dms = _get_dms_for_project(project_id)
    return dms.list_documents(project_id)


@router.post("/documents")
async def upload_document(
    file: UploadFile = File(...),
    project_id: str = Depends(get_project_id),
):
    """Upload a document to the active project."""
    dms = _get_dms_for_project(project_id)

    # Save uploaded file to a temp location
    suffix = os.path.splitext(file.filename or "upload.bin")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        doc_id = dms.upload_document(project_id, tmp_path)
        if not doc_id:
            raise HTTPException(status_code=500, detail="Failed to upload document")
        return {"status": "ok", "document_id": doc_id, "filename": file.filename}
    finally:
        # Clean up temp file
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


@router.delete("/documents/{document_id}")
def delete_document(document_id: str):
    """Delete a document."""
    # Try all cached DMS instances
    for dms in _dms_cache.values():
        result = dms.delete_document(document_id)
        if result:
            return {"status": "ok", "deleted": document_id}
    raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")


# --- RAG Context ---


@router.post("/documents/{document_id}/rag")
def add_to_rag(document_id: str):
    """Add a document to manual RAG context."""
    for dms in _dms_cache.values():
        result = dms.add_to_rag_context(document_id)
        if result:
            return {"status": "ok", "added": document_id}
    raise HTTPException(status_code=400, detail="Document already in RAG context or not found")


@router.delete("/documents/{document_id}/rag")
def remove_from_rag(document_id: str):
    """Remove a document from manual RAG context."""
    for dms in _dms_cache.values():
        result = dms.remove_from_rag_context(document_id)
        if result:
            return {"status": "ok", "removed": document_id}
    raise HTTPException(status_code=400, detail="Document not in RAG context")


@router.get("/rag/manual")
def list_manual_rag(
    project_id: str = Depends(get_project_id),
):
    """List document IDs in manual RAG context."""
    dms = _get_dms_for_project(project_id)
    return {"document_ids": dms.list_manual_rag_documents()}


@router.get("/rag/search")
def search_rag(
    query: str,
    k: int = 5,
    project_id: str = Depends(get_project_id),
):
    """Search RAG context for relevant chunks."""
    dms = _get_dms_for_project(project_id)
    results = dms.get_rag_context(query, project_id=project_id, k=k)
    return {"results": results}
