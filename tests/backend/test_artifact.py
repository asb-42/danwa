"""Tests for DebateArtifact and inner transcript models."""

from __future__ import annotations

from datetime import UTC, datetime

from backend.models.artifact import (
    DebateArtifact,
    Injection,
    MinorityVote,
    Turn,
    UserQuery,
)


class TestTurn:
    def test_minimal(self) -> None:
        t = Turn(round=1, node_id="n1", agent_name="Alice", role_type="strategist", content="Hello")
        assert t.round == 1
        assert t.agent_name == "Alice"
        assert t.id  # auto-generated

    def test_with_all_fields(self) -> None:
        t = Turn(
            id="turn-1",
            round=2,
            node_id="node-a",
            agent_name="Bob",
            role_type="critic",
            role_definition_id="rd-1",
            llm_profile_id="27e9f4f7-7302-4d0b-8043-9b4edd8c882c",
            content="I disagree",
            timestamp=datetime(2025, 1, 1, tzinfo=UTC),
            latency_ms=150,
            token_usage={"prompt": 100, "completion": 50, "total": 150},
        )
        assert t.id == "turn-1"
        assert t.token_usage["total"] == 150


class TestInjection:
    def test_minimal(self) -> None:
        inj = Injection(target_node_id="n1", content="Consider X")
        assert inj.source == "user"
        assert inj.id

    def test_system_source(self) -> None:
        inj = Injection(source="system", target_node_id="n2", content="Auto-inject")
        assert inj.source == "system"


class TestUserQuery:
    def test_minimal(self) -> None:
        q = UserQuery(content="What about Y?")
        assert q.response_turn_id is None

    def test_with_response(self) -> None:
        q = UserQuery(content="Why?", response_turn_id="turn-42")
        assert q.response_turn_id == "turn-42"


class TestMinorityVote:
    def test_minimal(self) -> None:
        v = MinorityVote(agent_name="Critic", dissent_content="I disagree", target_turn_id="turn-1")
        assert v.agent_name == "Critic"


class TestDebateArtifact:
    def test_minimal(self) -> None:
        a = DebateArtifact(session_id="s1", workflow_id="w1")
        assert a.session_id == "s1"
        assert a.transcript == []
        assert a.consensus_result is None

    def test_with_transcript(self) -> None:
        turns = [
            Turn(round=1, node_id="n1", agent_name="A", role_type="strategist", content="Arg1"),
            Turn(round=1, node_id="n2", agent_name="B", role_type="critic", content="Arg2"),
        ]
        a = DebateArtifact(
            session_id="s1",
            workflow_id="w1",
            topic="Test Topic",
            transcript=turns,
        )
        assert len(a.transcript) == 2
        assert a.topic == "Test Topic"

    def test_artifact_hash_deterministic(self) -> None:
        a = DebateArtifact(session_id="s1", workflow_id="w1", topic="T")
        h1 = a.artifact_hash()
        h2 = a.artifact_hash()
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_artifact_hash_differs_for_different_artifacts(self) -> None:
        a1 = DebateArtifact(session_id="s1", workflow_id="w1")
        a2 = DebateArtifact(session_id="s2", workflow_id="w1")
        assert a1.artifact_hash() != a2.artifact_hash()

    def test_full_model(self) -> None:
        a = DebateArtifact(
            session_id="s1",
            workflow_id="w1",
            workflow_version=2,
            workflow_name="My Workflow",
            topic="AI Ethics",
            tone_profile_snapshot={"style": "academic"},
            transcript=[
                Turn(round=1, node_id="n1", agent_name="A", role_type="strategist", content="C"),
            ],
            interjections=[
                Injection(target_node_id="n1", content="Extra info"),
            ],
            user_queries=[
                UserQuery(content="Why?"),
            ],
            minority_votes=[
                MinorityVote(agent_name="B", dissent_content="No", target_turn_id="t1"),
            ],
            consensus_result={"score": 0.9},
            metadata={"token_usage": {"total": 1000}},
        )
        assert a.workflow_version == 2
        assert len(a.interjections) == 1
        assert len(a.user_queries) == 1
        assert len(a.minority_votes) == 1
        assert a.consensus_result["score"] == 0.9
