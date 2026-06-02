"""Tests for the DMS API endpoints (documents, RAG context)."""

from __future__ import annotations

import io

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_text_file(name: str = "test.txt", content: str = "Hello world") -> tuple:
    """Create a fake upload file tuple for TestClient."""
    return ("file", (name, io.BytesIO(content.encode()), "text/plain"))


# ---------------------------------------------------------------------------
# DMS API — Document CRUD
# ---------------------------------------------------------------------------


class TestDMSListDocuments:
    """GET /api/v1/dms/documents"""

    def test_list_documents_returns_empty(self, client):
        """When no documents exist, returns empty list."""
        response = client.get("/api/v1/dms/documents")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_documents_returns_200(self, client):
        """Endpoint is accessible and returns a list."""
        response = client.get("/api/v1/dms/documents")
        assert response.status_code == 200
        assert isinstance(response.json(), list)


class TestDMSUploadDocument:
    """POST /api/v1/dms/documents"""

    def test_upload_document_returns_200(self, client):
        """Upload a text file and get back a document ID."""
        files = [_make_text_file("upload_test.txt", "Some test content for upload")]
        response = client.post("/api/v1/dms/documents", files=files)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "document_id" in data
        assert data["filename"] == "upload_test.txt"

    def test_upload_document_appears_in_list(self, client):
        """After upload, document appears in list."""
        files = [_make_text_file("listed.txt", "Content for listing test")]
        upload_resp = client.post("/api/v1/dms/documents", files=files)
        doc_id = upload_resp.json()["document_id"]

        list_resp = client.get("/api/v1/dms/documents")
        docs = list_resp.json()
        # The list response uses 'id' as the key (from DMSDB.get_document)
        doc_ids = [d.get("id") or d.get("document_id") for d in docs]
        assert doc_id in doc_ids


class TestDMSDeleteDocument:
    """DELETE /api/v1/dms/documents/{document_id}"""

    def test_delete_document_returns_200(self, client):
        """Delete an existing document."""
        files = [_make_text_file("to_delete.txt", "Delete me")]
        upload_resp = client.post("/api/v1/dms/documents", files=files)
        doc_id = upload_resp.json()["document_id"]

        del_resp = client.delete(f"/api/v1/dms/documents/{doc_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == doc_id

    def test_delete_nonexistent_returns_200(self, client):
        """Deleting a non-existent document returns 200 (DMS delete is idempotent)."""
        response = client.delete("/api/v1/dms/documents/nonexistent-id")
        # DMS.delete_document always returns True (idempotent delete)
        assert response.status_code == 200

    def test_deleted_document_not_in_list(self, client):
        """After deletion, document no longer appears in list."""
        files = [_make_text_file("gone.txt", "Will be gone")]
        upload_resp = client.post("/api/v1/dms/documents", files=files)
        doc_id = upload_resp.json()["document_id"]

        client.delete(f"/api/v1/dms/documents/{doc_id}")

        list_resp = client.get("/api/v1/dms/documents")
        doc_ids = [d.get("id") or d.get("document_id") for d in list_resp.json()]
        assert doc_id not in doc_ids


# ---------------------------------------------------------------------------
# DMS API — RAG Context Management
# ---------------------------------------------------------------------------


class TestDMSRAGContext:
    """RAG context management endpoints."""

    def _upload_doc(self, client, name: str = "rag_doc.txt", content: str = "RAG content"):
        """Helper: upload a document and return its ID."""
        files = [_make_text_file(name, content)]
        resp = client.post("/api/v1/dms/documents", files=files)
        return resp.json()["document_id"]

    def test_add_to_rag_returns_200(self, client):
        """Add a document to manual RAG context."""
        doc_id = self._upload_doc(client)
        response = client.post(f"/api/v1/dms/documents/{doc_id}/rag")
        assert response.status_code == 200
        assert response.json()["added"] == doc_id

    def test_add_to_rag_nonexistent_returns_404(self, client):
        """Adding a non-existent (or foreign-project) document to RAG returns 404.

        Multi-tenant safety: we no longer accept arbitrary document_ids
        into the manual RAG set, so a caller cannot attach a document
        from another project to the active project's RAG selection.
        """
        response = client.post("/api/v1/dms/documents/nonexistent/rag")
        assert response.status_code == 404

    def test_remove_from_rag_returns_200(self, client):
        """Remove a document from manual RAG context."""
        doc_id = self._upload_doc(client)
        client.post(f"/api/v1/dms/documents/{doc_id}/rag")

        response = client.delete(f"/api/v1/dms/documents/{doc_id}/rag")
        assert response.status_code == 200
        assert response.json()["removed"] == doc_id

    def test_remove_from_rag_not_in_context_returns_400(self, client):
        """Removing a document not in RAG context returns 400."""
        doc_id = self._upload_doc(client, name="not_in_rag.txt")
        response = client.delete(f"/api/v1/dms/documents/{doc_id}/rag")
        assert response.status_code == 400

    def test_list_manual_rag_empty(self, client):
        """Manual RAG list is empty initially."""
        response = client.get("/api/v1/dms/rag/manual")
        assert response.status_code == 200
        assert response.json()["document_ids"] == []

    def test_list_manual_rag_after_add(self, client):
        """After adding a document, it appears in manual RAG list."""
        doc_id = self._upload_doc(client)
        client.post(f"/api/v1/dms/documents/{doc_id}/rag")

        response = client.get("/api/v1/dms/rag/manual")
        assert doc_id in response.json()["document_ids"]

    def test_list_manual_rag_after_remove(self, client):
        """After removing, document no longer in manual RAG list."""
        doc_id = self._upload_doc(client)
        client.post(f"/api/v1/dms/documents/{doc_id}/rag")
        client.delete(f"/api/v1/dms/documents/{doc_id}/rag")

        response = client.get("/api/v1/dms/rag/manual")
        assert doc_id not in response.json()["document_ids"]


class TestDMSRAGSearch:
    """GET /api/v1/dms/rag/search"""

    def test_search_rag_returns_200(self, client):
        """RAG search endpoint is accessible."""
        response = client.get("/api/v1/dms/rag/search", params={"query": "test"})
        assert response.status_code == 200
        assert "results" in response.json()

    def test_search_rag_with_limit(self, client):
        """RAG search respects k parameter."""
        response = client.get("/api/v1/dms/rag/search", params={"query": "test", "k": 3})
        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) <= 3
