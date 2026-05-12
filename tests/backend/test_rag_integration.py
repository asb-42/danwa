"""Tests for RAG integration in the debate API.

Covers:
- DebateRequest schema with document_ids and rag_auto_retrieve
- PUT /debate/{id}/documents endpoint
- RAG fields in GET /debate/{id} response
- _extract_rag_info() and _build_rag_preview() helpers
"""

from __future__ import annotations

import io

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _upload_doc(client, name: str = "rag_test.txt", content: str = "Test content for RAG") -> str:
    """Upload a document and return its ID."""
    files = [("file", (name, io.BytesIO(content.encode()), "text/plain"))]
    resp = client.post("/api/v1/dms/documents", files=files)
    assert resp.status_code == 200
    return resp.json()["document_id"]


# ---------------------------------------------------------------------------
# DebateRequest schema — RAG fields
# ---------------------------------------------------------------------------


class TestDebateRequestRAGFields:
    """Verify DebateRequest accepts document_ids and rag_auto_retrieve."""

    def test_create_debate_with_document_ids(self, client):
        """Creating a debate with document_ids returns 201."""
        response = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Debate with documents"},
                "document_ids": ["doc-1", "doc-2"],
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"

    def test_create_debate_with_rag_auto_retrieve(self, client):
        """Creating a debate with rag_auto_retrieve returns 201."""
        response = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Debate with auto-retrieve"},
                "rag_auto_retrieve": True,
            },
        )
        assert response.status_code == 201

    def test_create_debate_with_both_rag_fields(self, client):
        """Creating a debate with both RAG fields returns 201."""
        response = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Full RAG debate"},
                "document_ids": ["doc-1"],
                "rag_auto_retrieve": True,
            },
        )
        assert response.status_code == 201

    def test_create_debate_default_rag_fields(self, client):
        """Default RAG fields are empty list and False."""
        response = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Default RAG fields"}},
        )
        assert response.status_code == 201


# ---------------------------------------------------------------------------
# GET /debate/{id} — RAG fields in response
# ---------------------------------------------------------------------------


class TestGetDebateRAGFields:
    """Verify RAG fields appear in debate status response."""

    def test_get_debate_has_rag_fields(self, client):
        """Response includes rag_enabled, rag_document_count, rag_context_preview."""
        # Create debate
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "RAG fields test"}},
        )
        debate_id = create_resp.json()["debate_id"]

        # Get debate
        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        assert get_resp.status_code == 200
        data = get_resp.json()

        assert "rag_enabled" in data
        assert "rag_document_count" in data
        assert "rag_context_preview" in data
        assert data["rag_enabled"] is False
        assert data["rag_document_count"] == 0
        assert data["rag_context_preview"] == ""

    def test_get_debate_rag_enabled_with_documents(self, client):
        """When document_ids are set, rag_enabled is True."""
        doc_id = _upload_doc(client)

        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "RAG enabled test"},
                "document_ids": [doc_id],
            },
        )
        debate_id = create_resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()

        assert data["rag_enabled"] is True
        assert data["rag_document_count"] == 1

    def test_get_debate_rag_enabled_with_auto_retrieve(self, client):
        """When rag_auto_retrieve is True, rag_enabled is True."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Auto-retrieve test"},
                "rag_auto_retrieve": True,
            },
        )
        debate_id = create_resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()

        assert data["rag_enabled"] is True


# ---------------------------------------------------------------------------
# PUT /debate/{id}/documents — Assign documents to debate
# ---------------------------------------------------------------------------


class TestAssignDocumentsToDebate:
    """PUT /api/v1/debate/{debate_id}/documents"""

    def test_assign_documents_returns_200(self, client):
        """Assign documents to a pending debate."""
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Assign docs test"}},
        )
        debate_id = create_resp.json()["debate_id"]

        put_resp = client.put(
            f"/api/v1/debate/{debate_id}/documents",
            json={"document_ids": ["doc-a", "doc-b"], "rag_auto_retrieve": False},
        )
        assert put_resp.status_code == 200
        data = put_resp.json()
        assert data["debate_id"] == debate_id
        assert data["document_ids"] == ["doc-a", "doc-b"]
        assert data["rag_auto_retrieve"] is False

    def test_assign_documents_updates_get_response(self, client):
        """After assigning documents, GET response reflects the change."""
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Reflect docs test"}},
        )
        debate_id = create_resp.json()["debate_id"]

        client.put(
            f"/api/v1/debate/{debate_id}/documents",
            json={"document_ids": ["doc-x"], "rag_auto_retrieve": True},
        )

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()

        assert data["rag_enabled"] is True
        assert data["rag_document_count"] == 1

    def test_assign_documents_nonexistent_debate_returns_404(self, client):
        """Assigning to a non-existent debate returns 404."""
        response = client.put(
            "/api/v1/debate/nonexistent-id/documents",
            json={"document_ids": ["doc-1"]},
        )
        assert response.status_code == 404

    def test_assign_documents_empty_list(self, client):
        """Assigning an empty list clears documents."""
        create_resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Clear docs test"},
                "document_ids": ["doc-1"],
            },
        )
        debate_id = create_resp.json()["debate_id"]

        put_resp = client.put(
            f"/api/v1/debate/{debate_id}/documents",
            json={"document_ids": []},
        )
        assert put_resp.status_code == 200

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()
        assert data["rag_enabled"] is False
        assert data["rag_document_count"] == 0

    def test_assign_documents_with_auto_retrieve(self, client):
        """Assigning with rag_auto_retrieve=True."""
        create_resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "Auto-retrieve assign test"}},
        )
        debate_id = create_resp.json()["debate_id"]

        put_resp = client.put(
            f"/api/v1/debate/{debate_id}/documents",
            json={"document_ids": [], "rag_auto_retrieve": True},
        )
        assert put_resp.status_code == 200
        assert put_resp.json()["rag_auto_retrieve"] is True


# ---------------------------------------------------------------------------
# _extract_rag_info() — Unit-level via API
# ---------------------------------------------------------------------------


class TestExtractRAGInfo:
    """Test RAG info extraction through the API response."""

    def test_no_rag_fields_defaults(self, client):
        """Debate without RAG fields has rag_enabled=False."""
        resp = client.post(
            "/api/v1/debate",
            json={"case": {"text": "No RAG"}},
        )
        debate_id = resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()
        assert data["rag_enabled"] is False
        assert data["rag_document_count"] == 0
        assert data["rag_context_preview"] == ""

    def test_multiple_document_ids(self, client):
        """Multiple document_ids are counted correctly."""
        resp = client.post(
            "/api/v1/debate",
            json={
                "case": {"text": "Multi-doc"},
                "document_ids": ["a", "b", "c"],
            },
        )
        debate_id = resp.json()["debate_id"]

        get_resp = client.get(f"/api/v1/debate/{debate_id}")
        data = get_resp.json()
        assert data["rag_enabled"] is True
        assert data["rag_document_count"] == 3
