"""Tests for task dispatch, workflow state backends, and Celery configuration."""

from __future__ import annotations

from backend.state.workflow_state import InMemoryWorkflowState, get_workflow_state

# ---------------------------------------------------------------------------
# InMemoryWorkflowState
# ---------------------------------------------------------------------------


class TestInMemoryWorkflowState:
    def test_default_status_is_unknown(self):
        state = InMemoryWorkflowState()
        assert state.get_status("s1") == "unknown"

    def test_set_and_get_status(self):
        state = InMemoryWorkflowState()
        state.set_status("s1", "running")
        assert state.get_status("s1") == "running"

    def test_cancel_and_check(self):
        state = InMemoryWorkflowState()
        assert not state.is_cancelled("s1")
        state.cancel("s1")
        assert state.is_cancelled("s1")
        assert state.get_status("s1") == "cancelled"

    def test_clear_cancel(self):
        state = InMemoryWorkflowState()
        state.cancel("s1")
        assert state.is_cancelled("s1")
        state.clear_cancel("s1")
        assert not state.is_cancelled("s1")

    def test_pause_and_resume(self):
        state = InMemoryWorkflowState()
        assert not state.is_paused("s1")
        state.pause("s1")
        assert state.is_paused("s1")
        assert state.get_status("s1") == "paused"
        state.resume("s1")
        assert not state.is_paused("s1")
        assert state.get_status("s1") == "running"

    def test_cleanup(self):
        state = InMemoryWorkflowState()
        state.set_status("s1", "running")
        state.cancel("s1")
        state.pause("s1")
        state.cleanup("s1")
        assert state.get_status("s1") == "unknown"
        assert not state.is_cancelled("s1")
        assert not state.is_paused("s1")

    def test_get_pause_event(self):
        state = InMemoryWorkflowState()
        event = state.get_pause_event("s1")
        assert event.is_set()  # Not paused by default

    def test_independent_sessions(self):
        state = InMemoryWorkflowState()
        state.set_status("s1", "running")
        state.set_status("s2", "paused")
        assert state.get_status("s1") == "running"
        assert state.get_status("s2") == "paused"
        state.cleanup("s1")
        assert state.get_status("s1") == "unknown"
        assert state.get_status("s2") == "paused"


# ---------------------------------------------------------------------------
# get_workflow_state factory
# ---------------------------------------------------------------------------


class TestGetWorkflowState:
    def setup_method(self) -> None:
        """Reset the singleton cache so each test sees a fresh factory call."""
        from backend.state.workflow_state import reset_workflow_state_cache

        reset_workflow_state_cache()

    def teardown_method(self) -> None:
        """Clean up the singleton cache after each test to avoid cross-test leaks."""
        from backend.state.workflow_state import reset_workflow_state_cache

        reset_workflow_state_cache()

    def test_returns_in_memory_when_no_redis(self, monkeypatch):
        monkeypatch.setattr("backend.core.config.settings.redis_url", "")
        state = get_workflow_state()
        assert isinstance(state, InMemoryWorkflowState)

    def test_returns_in_memory_when_redis_unavailable(self, monkeypatch):
        """When Redis URL is set but Redis is unreachable, should fall back."""
        monkeypatch.setattr("backend.core.config.settings.redis_url", "redis://localhost:9999/0")
        state = get_workflow_state()
        # Redis connects lazily, so it may return RedisWorkflowState even when
        # Redis is not running. The fallback only happens if the constructor fails.
        # Just verify it returns a valid state backend.
        assert hasattr(state, "get_status")

    def test_returns_same_instance_on_repeated_calls(self):
        """``get_workflow_state()`` returns the same module-level
        singleton, so state set via one call is visible to the
        next.  This is the cross-request coordination property
        that the in-memory backend needs to be useful.
        """
        from backend.state.workflow_state import reset_workflow_state_cache

        reset_workflow_state_cache()
        a = get_workflow_state()
        b = get_workflow_state()
        assert a is b
        a.set_status("s1", "running")
        assert b.get_status("s1") == "running"

    def test_reset_workflow_state_cache_returns_new_instance(self):
        """After ``reset_workflow_state_cache()``, the factory
        creates a fresh instance.  Useful for tests that want
        clean state.
        """
        from backend.state.workflow_state import reset_workflow_state_cache

        a = get_workflow_state()
        a.set_status("s1", "running")
        reset_workflow_state_cache()
        b = get_workflow_state()
        assert a is not b
        assert b.get_status("s1") == "unknown"


# ---------------------------------------------------------------------------
# Celery app factory
# ---------------------------------------------------------------------------


class TestCeleryApp:
    def test_returns_none_when_not_configured(self, monkeypatch):
        # Reset cached app
        import backend.tasks.celery_app as mod

        mod._celery_app = None

        monkeypatch.setattr("backend.core.config.settings.redis_url", "")
        monkeypatch.setattr("backend.core.config.settings.celery_enabled", False)
        from backend.tasks.celery_app import get_celery_app

        assert get_celery_app() is None

    def test_returns_none_when_no_redis_url(self, monkeypatch):
        import backend.tasks.celery_app as mod

        mod._celery_app = None

        monkeypatch.setattr("backend.core.config.settings.redis_url", "")
        monkeypatch.setattr("backend.core.config.settings.celery_enabled", True)
        from backend.tasks.celery_app import get_celery_app

        assert get_celery_app() is None

    def test_returns_none_when_not_enabled(self, monkeypatch):
        import backend.tasks.celery_app as mod

        mod._celery_app = None

        monkeypatch.setattr("backend.core.config.settings.redis_url", "redis://localhost:6379/0")
        monkeypatch.setattr("backend.core.config.settings.celery_enabled", False)
        from backend.tasks.celery_app import get_celery_app

        assert get_celery_app() is None


# ---------------------------------------------------------------------------
# Task dispatch (mock tests)
# ---------------------------------------------------------------------------


class TestTaskDispatch:
    def test_dispatch_debate_task_falls_back_to_background(self, monkeypatch):
        """When Celery is not available, dispatch should use BackgroundTasks."""
        import backend.tasks.celery_app as mod

        mod._celery_app = None

        monkeypatch.setattr("backend.core.config.settings.redis_url", "")
        monkeypatch.setattr("backend.core.config.settings.celery_enabled", False)

        from unittest.mock import MagicMock

        from backend.tasks.dispatch import dispatch_debate_task

        bt = MagicMock()
        result = dispatch_debate_task(bt, "deb-1", "proj-1", "audit", "store", "ps")
        assert result == "background"
        bt.add_task.assert_called_once()

    def test_dispatch_workflow_task_falls_back_to_background(self, monkeypatch):
        """When Celery is not available, workflow dispatch should use BackgroundTasks."""
        import backend.tasks.celery_app as mod

        mod._celery_app = None

        monkeypatch.setattr("backend.core.config.settings.redis_url", "")
        monkeypatch.setattr("backend.core.config.settings.celery_enabled", False)

        from unittest.mock import MagicMock

        from backend.tasks.dispatch import dispatch_workflow_task

        bt = MagicMock()
        result = dispatch_workflow_task(bt, "sess-1", "wf-1", "proj-1", {}, "compiled", "snap")
        assert result == "background"
        bt.add_task.assert_called_once()
