"""API router for Document Management System (projects, documents, RAG)."""

import logging
import os
import tempfile

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from src.dms.dms import DMS

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-init DMS singleton (heavy: ChromaDB, SQLite)
_dms: DMS | None = None


def get_dms() -> DMS:
    global _dms
    if _dms is None:
        _dms = DMS()
    return _dms


class ProjectBody(BaseModel):
    name: str
    description: str = ""


# --- Projects ---


@router.get("/projects")
def list_projects():
    """List all DMS projects."""
    dms = get_dms()
    return dms.list_projects()


@router.post("/projects")
def create_project(body: ProjectBody):
    """Create a new DMS project."""
    dms = get_dms()
    project_id = dms.create_project(body.name, body.description)
    if not project_id:
        raise HTTPException(status_code=500, detail="Failed to create project")
    return {"status": "ok", "project_id": project_id}


@router.delete("/projects/{project_id}")
def delete_project(project_id: str):
    """Delete a DMS project."""
    dms = get_dms()
    result = dms.delete_project(project_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found")
    return {"status": "ok", "deleted": project_id}


# --- Documents ---


@router.get("/projects/{project_id}/documents")
def list_documents(project_id: str):
    """List documents in a project."""
    dms = get_dms()
    return dms.list_documents(project_id)


@router.post("/projects/{project_id}/documents")
async def upload_document(project_id: str, file: UploadFile = File(...)):
    """Upload a document to a project."""
    dms = get_dms()

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
    dms = get_dms()
    result = dms.delete_document(document_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Document '{document_id}' not found")
    return {"status": "ok", "deleted": document_id}


# --- RAG Context ---


@router.post("/documents/{document_id}/rag")
def add_to_rag(document_id: str):
    """Add a document to manual RAG context."""
    dms = get_dms()
    result = dms.add_to_rag_context(document_id)
    if not result:
        raise HTTPException(status_code=400, detail="Document already in RAG context or not found")
    return {"status": "ok", "added": document_id}


@router.delete("/documents/{document_id}/rag")
def remove_from_rag(document_id: str):
    """Remove a document from manual RAG context."""
    dms = get_dms()
    result = dms.remove_from_rag_context(document_id)
    if not result:
        raise HTTPException(status_code=400, detail="Document not in RAG context")
    return {"status": "ok", "removed": document_id}


@router.get("/rag/manual")
def list_manual_rag():
    """List document IDs in manual RAG context."""
    dms = get_dms()
    return {"document_ids": dms.list_manual_rag_documents()}


@router.get("/rag/search")
def search_rag(query: str, project_id: str | None = None, k: int = 5):
    """Search RAG context for relevant chunks."""
    dms = get_dms()
    results = dms.get_rag_context(query, project_id=project_id, k=k)
    return {"results": results}
