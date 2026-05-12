"""Tests for Phase 2 Group G.4 — StateSnapshotStore.

Covers save/get_latest roundtrip, get_history ordering, get_by_node,
and multi-session isolation.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.workflow.state_snapshot import StateSnapshotStore


@pytest.fixture()
def store(tmp_path: Path) -> StateSnapshotStore:
    """Fresh StateSnapshotStore with a temp database."""
    return StateSnapshotStore(db_path=tmp_path / "test_snapshots.db")


# ---------------------------------------------------------------------------
# save / get_latest roundtrip
# ---------------------------------------------------------------------------


class TestSaveGetLatest:
    """Test save() and get_latest() roundtrip."""

    def test_save_and_get_latest(self, store: StateSnapshotStore) -> None:
        """save() followed by get_latest() should return the saved snapshot."""
        store.save(
            session_id="sess-1",
            workflow_id="wf-1",
            node_id="node-a",
            node_type="wf-strategist",
            round_number=1,
            state_dict={"context": "test", "current_round": 1},
        )

        latest = store.get_latest("sess-1")
        assert latest is not None
        assert latest["session_id"] == "sess-1"
        assert latest["workflow_id"] == "wf-1"
        assert latest["node_id"] == "node-a"
        assert latest["node_type"] == "wf-strategist"
        assert latest["round_number"] == 1
        assert latest["state"]["context"] == "test"

    def test_get_latest_returns_most_recent(self, store: StateSnapshotStore) -> None:
        """get_latest() should return the most recent snapshot."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"round": 1})
        store.save("sess-1", "wf-1", "node-b", "wf-critic", 1, {"round": 1})
        store.save("sess-1", "wf-1", "node-c", "wf-optimizer", 2, {"round": 2})

        latest = store.get_latest("sess-1")
        assert latest is not None
        assert latest["node_id"] == "node-c"
        assert latest["round_number"] == 2

    def test_get_latest_nonexistent_session(self, store: StateSnapshotStore) -> None:
        """get_latest() for a nonexistent session returns None."""
        result = store.get_latest("nonexistent")
        assert result is None


# ---------------------------------------------------------------------------
# get_history
# ---------------------------------------------------------------------------


class TestGetHistory:
    """Test get_history() returns ordered snapshots."""

    def test_history_returns_all_snapshots(self, store: StateSnapshotStore) -> None:
        """get_history() should return all snapshots for a session."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"step": 1})
        store.save("sess-1", "wf-1", "node-b", "wf-critic", 1, {"step": 2})
        store.save("sess-1", "wf-1", "node-c", "wf-optimizer", 1, {"step": 3})

        history = store.get_history("sess-1")
        assert len(history) == 3

    def test_history_is_chronological(self, store: StateSnapshotStore) -> None:
        """get_history() should return snapshots in chronological order."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"step": 1})
        store.save("sess-1", "wf-1", "node-b", "wf-critic", 1, {"step": 2})
        store.save("sess-1", "wf-1", "node-c", "wf-optimizer", 1, {"step": 3})

        history = store.get_history("sess-1")
        node_ids = [h["node_id"] for h in history]
        assert node_ids == ["node-a", "node-b", "node-c"]

    def test_history_empty_session(self, store: StateSnapshotStore) -> None:
        """get_history() for an empty session returns empty list."""
        history = store.get_history("nonexistent")
        assert history == []


# ---------------------------------------------------------------------------
# get_by_node
# ---------------------------------------------------------------------------


class TestGetByNode:
    """Test get_by_node() returns the correct snapshot."""

    def test_get_by_node_returns_correct_snapshot(self, store: StateSnapshotStore) -> None:
        """get_by_node() should return the snapshot for a specific node."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"data": "a"})
        store.save("sess-1", "wf-1", "node-b", "wf-critic", 1, {"data": "b"})

        result = store.get_by_node("sess-1", "node-a")
        assert result is not None
        assert result["node_id"] == "node-a"
        assert result["state"]["data"] == "a"

    def test_get_by_node_nonexistent(self, store: StateSnapshotStore) -> None:
        """get_by_node() for a nonexistent node returns None."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {})
        result = store.get_by_node("sess-1", "node-z")
        assert result is None

    def test_get_by_node_returns_latest_for_node(self, store: StateSnapshotStore) -> None:
        """get_by_node() should return the latest snapshot for a node
        if it appears multiple times (e.g. in a feedback loop)."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"round": 1})
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 2, {"round": 2})

        result = store.get_by_node("sess-1", "node-a")
        assert result is not None
        assert result["round_number"] == 2


# ---------------------------------------------------------------------------
# Multi-session isolation
# ---------------------------------------------------------------------------


class TestSessionIsolation:
    """Test that sessions are properly isolated."""

    def test_sessions_are_isolated(self, store: StateSnapshotStore) -> None:
        """Snapshots in one session should not appear in another."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {"s": 1})
        store.save("sess-2", "wf-1", "node-b", "wf-critic", 1, {"s": 2})

        history_1 = store.get_history("sess-1")
        history_2 = store.get_history("sess-2")

        assert len(history_1) == 1
        assert len(history_2) == 1
        assert history_1[0]["node_id"] == "node-a"
        assert history_2[0]["node_id"] == "node-b"

    def test_get_latest_isolation(self, store: StateSnapshotStore) -> None:
        """get_latest() should only return from the specified session."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {})
        store.save("sess-2", "wf-1", "node-b", "wf-critic", 1, {})

        latest_1 = store.get_latest("sess-1")
        latest_2 = store.get_latest("sess-2")

        assert latest_1["node_id"] == "node-a"
        assert latest_2["node_id"] == "node-b"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Test edge cases for StateSnapshotStore."""

    def test_state_with_complex_data(self, store: StateSnapshotStore) -> None:
        """State dict with nested structures should roundtrip correctly."""
        complex_state = {
            "context": "test",
            "node_outputs": [
                {"node_id": "a", "content": "hello"},
                {"node_id": "b", "content": "world"},
            ],
            "metadata": {"key": "value", "nested": {"a": 1}},
        }
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, complex_state)

        latest = store.get_latest("sess-1")
        assert latest["state"]["node_outputs"][0]["content"] == "hello"
        assert latest["state"]["metadata"]["nested"]["a"] == 1

    def test_empty_state_dict(self, store: StateSnapshotStore) -> None:
        """Empty state dict should roundtrip correctly."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {})
        latest = store.get_latest("sess-1")
        assert latest["state"] == {}

    def test_created_at_is_set(self, store: StateSnapshotStore) -> None:
        """created_at should be automatically set."""
        store.save("sess-1", "wf-1", "node-a", "wf-strategist", 1, {})
        latest = store.get_latest("sess-1")
        assert "created_at" in latest
        assert latest["created_at"]  # Non-empty string
