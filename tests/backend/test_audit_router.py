"""Tests for backend/api/routers/audit.py — audit-event endpoint.

The router had 15 % coverage.  These tests focus on the endpoint
contract and the pure helper functions ``_enrich_events_with_debate_data``
and ``_resolve_debate_id`` plus the documented MVP fallback path
(recently added in commit faba456).
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi.testclient import TestClient

from backend.api.routers import audit as audit_module
from backend.api.routers.audit import (
    _enrich_events_with_debate_data,
    _resolve_debate_id,
    _transform_workflow_audit_events,
)
from backend.models.schemas import AgentRole, AuditEvent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(debate_id: str, round_num: int, agent: AgentRole, action: str = "agent_output") -> AuditEvent:
    return AuditEvent(
        debate_id=debate_id,
        round=round_num,
        agent=agent,
        action=action,
        timestamp=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# _enrich_events_with_debate_data
# ---------------------------------------------------------------------------


class TestEnrichEventsWithDebateData:
    def test_no_debate_data_returns_events_unchanged(self) -> None:
        events = [{"round": 1, "agent": "strategist", "action": "agent_output"}]
        assert _enrich_events_with_debate_data(events, None) == events

    def test_enrich_matches_round_and_agent(self) -> None:
        events = [
            {"round": 1, "agent": "strategist", "action": "agent_output"},
            {"round": 2, "agent": "critic", "action": "agent_output"},
        ]
        debate_data = {
            "rounds": [
                {
                    "round": 1,
                    "agent_outputs": [
                        {
                            "role": "strategist",
                            "content": "Plan A",
                            "tokens_used": 100,
                        }
                    ],
                },
                {
                    "round": 2,
                    "agent_outputs": [{"role": "critic", "content": "Counter A", "tokens_used": 80}],
                },
            ]
        }
        enriched = _enrich_events_with_debate_data(events, debate_data)
        assert enriched[0]["content"] == "Plan A"
        assert enriched[0]["tokens_used"] == 100
        assert enriched[1]["content"] == "Counter A"
        assert enriched[1]["tokens_used"] == 80

    def test_falls_back_to_result_rounds(self) -> None:
        # When ``rounds`` is empty, look at result.rounds
        events = [{"round": 1, "agent": "strategist", "action": "agent_output"}]
        debate_data = {
            "result": {
                "rounds": [
                    {
                        "round": 1,
                        "agent_outputs": [{"role": "strategist", "content": "X", "tokens_used": 5}],
                    }
                ]
            }
        }
        enriched = _enrich_events_with_debate_data(events, debate_data)
        assert enriched[0]["content"] == "X"

    def test_unmatched_event_stays_unchanged(self) -> None:
        events = [{"round": 5, "agent": "ghost", "action": "noop"}]
        debate_data = {
            "rounds": [
                {
                    "round": 1,
                    "agent_outputs": [{"role": "strategist", "content": "A", "tokens_used": 1}],
                }
            ]
        }
        enriched = _enrich_events_with_debate_data(events, debate_data)
        # The event keeps its shape and gets no content/tokens
        assert enriched[0] == {"round": 5, "agent": "ghost", "action": "noop"}
        assert "content" not in enriched[0]

    def test_agent_output_with_no_match_uses_round_fallback(self) -> None:
        # agent_output action with no (round, agent) match tries round-only match
        events = [
            {"round": 1, "agent": "wrong-role", "action": "agent_output"},
        ]
        debate_data = {
            "rounds": [
                {
                    "round": 1,
                    "agent_outputs": [{"role": "strategist", "content": "F", "tokens_used": 11}],
                }
            ]
        }
        enriched = _enrich_events_with_debate_data(events, debate_data)
        assert enriched[0]["content"] == "F"
        assert enriched[0]["tokens_used"] == 11

    def test_empty_rounds_keeps_events_unchanged(self) -> None:
        events = [{"round": 1, "agent": "a", "action": "x"}]
        debate_data = {"rounds": []}
        enriched = _enrich_events_with_debate_data(events, debate_data)
        assert enriched == events

    def test_does_not_mutate_input_events(self) -> None:
        events = [{"round": 1, "agent": "strategist", "action": "agent_output"}]
        debate_data = {
            "rounds": [
                {
                    "round": 1,
                    "agent_outputs": [{"role": "strategist", "content": "X", "tokens_used": 1}],
                }
            ]
        }
        _enrich_events_with_debate_data(events, debate_data)
        # Input event is untouched
        assert "content" not in events[0]


# ---------------------------------------------------------------------------
# _transform_workflow_audit_events
# ---------------------------------------------------------------------------


class TestTransformWorkflowAuditEvents:
    def test_node_completed(self) -> None:
        wf = [
            {
                "event_type": "node_completed",
                "node_id": "n1",
                "actor": "critic",
                "timestamp": "2026-01-01T00:00:00",
                "llm_profile_id": "claude",
                "completion_tokens": 42,
                "output_content": "hello",
            }
        ]
        out = _transform_workflow_audit_events(wf)
        assert len(out) == 1
        e = out[0]
        assert e["action"] == "node_completed (n1)"
        assert e["agent"] == "critic"
        assert e["llm_model"] == "claude"
        assert e["tokens_used"] == 42
        assert e["content"] == "hello"

    def test_node_started(self) -> None:
        wf = [
            {
                "event_type": "node_started",
                "node_id": "n2",
                "actor": "strategist",
                "timestamp": "2026-01-01T00:00:00",
            }
        ]
        out = _transform_workflow_audit_events(wf)
        assert out[0]["action"] == "node_started (n2)"
        assert out[0]["content"] == ""
        assert out[0]["tokens_used"] == 0
        assert out[0]["llm_model"] == ""

    def test_node_failed(self) -> None:
        wf = [
            {
                "event_type": "node_failed",
                "node_id": "n3",
                "actor": "moderator",
                "timestamp": "2026-01-01T00:00:00",
                "output_content": "boom",
            }
        ]
        out = _transform_workflow_audit_events(wf)
        assert out[0]["action"] == "node_failed (n3)"
        assert out[0]["content"] == "boom"

    def test_unknown_event_type_passes_through(self) -> None:
        wf = [
            {
                "event_type": "custom_event",
                "node_id": "n4",
                "actor": "x",
                "timestamp": "2026-01-01T00:00:00",
                "output_content": "raw",
            }
        ]
        out = _transform_workflow_audit_events(wf)
        assert out[0]["action"] == "custom_event"
        assert out[0]["content"] == "raw"
        assert out[0]["llm_model"] == ""
        assert out[0]["tokens_used"] == 0

    def test_empty_wf_events(self) -> None:
        assert _transform_workflow_audit_events([]) == []

    def test_session_id_enriches_llm_name_map(self, monkeypatch) -> None:
        # When session_id is provided, the function tries to load the
        # report_generator enrichment maps.  We monkeypatch them to a
        # controlled value to verify the merge.
        import backend.workflow.report_generator as rg

        monkeypatch.setattr(rg, "_build_node_llm_name_map", lambda _sid: {"n5": "friendly-llm"})
        monkeypatch.setattr(rg, "_build_audit_context_map", lambda _sid: {"n5": {"round": 7, "phase": "x"}})
        wf = [
            {
                "event_type": "node_completed",
                "node_id": "n5",
                "actor": "critic",
                "timestamp": "2026-01-01T00:00:00",
                "llm_profile_id": "fallback",
                "completion_tokens": 0,
                "output_content": "",
            }
        ]
        out = _transform_workflow_audit_events(wf, session_id="s-1")
        # The enriched name overrides the llm_profile_id fallback
        assert out[0]["llm_model"] == "friendly-llm"
        assert out[0]["round"] == 7
        assert out[0]["phase"] == "x"


# ---------------------------------------------------------------------------
# /api/v1/audit/{id} endpoint
# ---------------------------------------------------------------------------


class TestGetAuditEventsEndpoint:
    def test_unknown_debate_returns_empty_list(self, client: TestClient) -> None:
        resp = client.get("/api/v1/audit/no-such-debate")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_debate_id_with_audit_events(self, client: TestClient, audit_service) -> None:
        ev = _make_event("deb-1", 1, AgentRole.STRATEGIST)
        audit_service.record(ev, project_id="proj-1")
        resp = client.get("/api/v1/audit/deb-1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["agent"] == "strategist"
        assert data[0]["round"] == 1
        assert data[0]["action"] == "agent_output"

    def test_title_resolution_exact(self, client: TestClient, debate_store, monkeypatch) -> None:
        # Seed a debate and stub get_debate_store_for_case to return our store
        debate_store.put(
            "deb-2",
            {
                "title": "Unique Title X",
                "rounds": [],
                "result": {},
            },
        )
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        resp = client.get("/api/v1/audit/Unique Title X")
        assert resp.status_code == 200
        # Empty audit events for this debate — returns []
        assert resp.json() == []

    def test_title_resolution_partial(self, client: TestClient, debate_store, monkeypatch) -> None:
        debate_store.put(
            "deb-3",
            {"title": "Climate Policy 2026", "rounds": [], "result": {}},
        )
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        # Partial match (case-insensitive)
        resp = client.get("/api/v1/audit/climate")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_unknown_title_returns_empty(self, client: TestClient) -> None:
        resp = client.get("/api/v1/audit/Never%20Matches%20Anything")
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# /api/v1/audit/project/{project_id} endpoint
# ---------------------------------------------------------------------------


class TestGetAuditEventsByProjectEndpoint:
    def test_empty_project(self, client: TestClient) -> None:
        resp = client.get("/api/v1/audit/project/proj-empty?limit=10&offset=0")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_events_for_project(self, client: TestClient, audit_service) -> None:
        ev1 = _make_event("d1", 1, AgentRole.CRITIC)
        ev2 = _make_event("d2", 1, AgentRole.OPTIMIZER)
        audit_service.record(ev1, project_id="proj-A")
        audit_service.record(ev2, project_id="proj-B")

        resp = client.get("/api/v1/audit/project/proj-A")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["debate_id"] == "d1"
        assert data[0]["agent"] == "critic"

    def test_pagination_passthrough(self, client: TestClient, audit_service) -> None:
        for i in range(5):
            audit_service.record(
                _make_event(f"d{i}", 1, AgentRole.MODERATOR),
                project_id="proj-page",
            )
        resp = client.get("/api/v1/audit/project/proj-page?limit=2&offset=1")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


# ---------------------------------------------------------------------------
# _resolve_debate_id — direct exercise of the helper
# ---------------------------------------------------------------------------


class TestResolveDebateIdHelper:
    def test_direct_id_lookup(self, monkeypatch, debate_store) -> None:
        debate_store.put("d-direct", {"title": "X", "rounds": [], "result": {}})
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        d_id, d_data = _resolve_debate_id("d-direct", "p")
        assert d_id == "d-direct"
        assert d_data is not None and d_data["title"] == "X"

    def test_exact_title_match(self, monkeypatch, debate_store) -> None:
        debate_store.put("d-title", {"title": "My Title", "rounds": [], "result": {}})
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        d_id, d_data = _resolve_debate_id("My Title", "p")
        assert d_id == "d-title"

    def test_partial_title_match(self, monkeypatch, debate_store) -> None:
        debate_store.put("d-partial", {"title": "Long Title With Keyword", "rounds": [], "result": {}})
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        d_id, _ = _resolve_debate_id("keyword", "p")
        assert d_id == "d-partial"

    def test_not_found_returns_original(self, monkeypatch, debate_store) -> None:
        monkeypatch.setattr(audit_module, "get_debate_store_for_case", lambda _pid: debate_store)
        d_id, d_data = _resolve_debate_id("nope", "p")
        assert d_id == "nope"
        assert d_data is None
