"""Tests for the debate API endpoints."""

from __future__ import annotations


class TestCreateDebate:
    def test_create_debate_returns_201(self, client):
        response = client.post("/api/v1/debate", json={
            "case": {"text": "Test case for debate creation"}
        })
        assert response.status_code == 201
        data = response.json()
        assert "debate_id" in data
        assert data["status"] == "pending"

    def test_create_debate_has_uuid(self, client):
        import uuid
        response = client.post("/api/v1/debate", json={
            "case": {"text": "UUID test"}
        })
        debate_id = response.json()["debate_id"]
        uuid.UUID(debate_id)  # raises if invalid

    def test_create_debate_with_custom_params(self, client):
        response = client.post("/api/v1/debate", json={
            "case": {"text": "Custom params test"},
            "max_rounds": 5,
            "consensus_threshold": 0.9,
            "agent_profile": [
                {"role": "strategist", "temperature": 0.5},
                {"role": "critic", "temperature": 0.3},
            ]
        })
        assert response.status_code == 201

    def test_create_debate_empty_text_rejected(self, client):
        response = client.post("/api/v1/debate", json={
            "case": {"text": ""}
        })
        assert response.status_code == 422

    def test_create_debate_missing_case_rejected(self, client):
        response = client.post("/api/v1/debate", json={})
        assert response.status_code == 422


class TestGetDebate:
    def test_get_existing_debate(self, client):
        create_resp = client.post("/api/v1/debate", json={
            "case": {"text": "Get test"}
        })
        debate_id = create_resp.json()["debate_id"]

        response = client.get(f"/api/v1/debate/{debate_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["debate_id"] == debate_id
        assert data["status"] == "pending"
        assert data["current_round"] == 0

    def test_get_nonexistent_debate_returns_404(self, client):
        response = client.get("/api/v1/debate/nonexistent-id")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestStartDebate:
    def test_start_debate_runs_to_completion(self, client):
        create_resp = client.post("/api/v1/debate", json={
            "case": {"text": "Start test"},
            "max_rounds": 2,
            "consensus_threshold": 0.5,
        })
        debate_id = create_resp.json()["debate_id"]

        response = client.post(f"/api/v1/debate/{debate_id}/start")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["current_round"] > 0
        assert data["consensus_score"] is not None

    def test_start_nonexistent_debate_returns_404(self, client):
        response = client.post("/api/v1/debate/nonexistent-id/start")
        assert response.status_code == 404

    def test_start_already_started_returns_409(self, client):
        create_resp = client.post("/api/v1/debate", json={
            "case": {"text": "Double start test"},
            "max_rounds": 1,
            "consensus_threshold": 0.5,
        })
        debate_id = create_resp.json()["debate_id"]

        client.post(f"/api/v1/debate/{debate_id}/start")
        response = client.post(f"/api/v1/debate/{debate_id}/start")
        assert response.status_code == 409

    def test_started_debate_has_rounds(self, client):
        create_resp = client.post("/api/v1/debate", json={
            "case": {"text": "Rounds test"},
            "max_rounds": 2,
            "consensus_threshold": 0.5,
        })
        debate_id = create_resp.json()["debate_id"]

        start_resp = client.post(f"/api/v1/debate/{debate_id}/start")
        data = start_resp.json()
        assert len(data["rounds"]) > 0

    def test_started_debate_creates_audit_events(self, client, audit_service):
        create_resp = client.post("/api/v1/debate", json={
            "case": {"text": "Audit test"},
            "max_rounds": 1,
            "consensus_threshold": 0.5,
        })
        debate_id = create_resp.json()["debate_id"]

        client.post(f"/api/v1/debate/{debate_id}/start")
        events = audit_service.get_events(debate_id)
        assert len(events) > 0
        assert events[0]["debate_id"] == debate_id
