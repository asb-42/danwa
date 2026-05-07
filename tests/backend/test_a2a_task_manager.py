"""Tests for A2A TaskManager — SQLite-backed persistent task store."""

from __future__ import annotations

import pytest

from backend.a2a.task_manager import TaskManager, TaskStatus


@pytest.fixture()
def task_manager(tmp_path) -> TaskManager:
    """Isolated TaskManager with a temporary database."""
    return TaskManager(db_path=tmp_path / "test_a2a_tasks.db")


# ------------------------------------------------------------------
# Create
# ------------------------------------------------------------------


class TestCreateTask:
    def test_create_task_returns_dict(self, task_manager: TaskManager):
        task = task_manager.create_task("task-1")
        assert task["id"] == "task-1"
        assert task["status"] == TaskStatus.SUBMITTED
        assert task["debate_id"] is None
        assert task["result"] is None
        assert task["error"] is None
        assert "created_at" in task
        assert "updated_at" in task

    def test_create_task_with_custom_status(self, task_manager: TaskManager):
        task = task_manager.create_task("task-2", status=TaskStatus.WORKING)
        assert task["status"] == TaskStatus.WORKING

    def test_create_task_persists(self, task_manager: TaskManager):
        task_manager.create_task("task-3")
        retrieved = task_manager.get_task("task-3")
        assert retrieved is not None
        assert retrieved["id"] == "task-3"


# ------------------------------------------------------------------
# Get
# ------------------------------------------------------------------


class TestGetTask:
    def test_get_existing_task(self, task_manager: TaskManager):
        task_manager.create_task("task-10")
        task = task_manager.get_task("task-10")
        assert task is not None
        assert task["id"] == "task-10"

    def test_get_nonexistent_task_returns_none(self, task_manager: TaskManager):
        assert task_manager.get_task("nonexistent") is None


# ------------------------------------------------------------------
# Update
# ------------------------------------------------------------------


class TestUpdateTask:
    def test_update_status(self, task_manager: TaskManager):
        task_manager.create_task("task-20")
        updated = task_manager.update_task("task-20", status=TaskStatus.WORKING)
        assert updated is not None
        assert updated["status"] == TaskStatus.WORKING

    def test_update_debate_id(self, task_manager: TaskManager):
        task_manager.create_task("task-21")
        updated = task_manager.update_task("task-21", debate_id="debate-abc")
        assert updated is not None
        assert updated["debate_id"] == "debate-abc"

    def test_update_result(self, task_manager: TaskManager):
        task_manager.create_task("task-22")
        updated = task_manager.update_task(
            "task-22",
            status=TaskStatus.COMPLETED,
            result="Debate result text",
        )
        assert updated is not None
        assert updated["status"] == TaskStatus.COMPLETED
        assert updated["result"] == "Debate result text"

    def test_update_error(self, task_manager: TaskManager):
        task_manager.create_task("task-23")
        updated = task_manager.update_task(
            "task-23",
            status=TaskStatus.FAILED,
            error="Something went wrong",
        )
        assert updated is not None
        assert updated["status"] == TaskStatus.FAILED
        assert updated["error"] == "Something went wrong"

    def test_update_nonexistent_returns_none(self, task_manager: TaskManager):
        result = task_manager.update_task("nonexistent", status=TaskStatus.FAILED)
        assert result is None

    def test_update_bumps_updated_at(self, task_manager: TaskManager):
        task_manager.create_task("task-24")
        original = task_manager.get_task("task-24")
        updated = task_manager.update_task("task-24", status=TaskStatus.WORKING)
        assert updated is not None
        assert updated["updated_at"] >= original["updated_at"]


# ------------------------------------------------------------------
# Status transitions
# ------------------------------------------------------------------


class TestStatusTransitions:
    def test_full_lifecycle(self, task_manager: TaskManager):
        """submitted → working → completed."""
        task_manager.create_task("task-30")
        task_manager.update_task("task-30", status=TaskStatus.WORKING)
        task_manager.update_task("task-30", status=TaskStatus.COMPLETED, result="done")

        task = task_manager.get_task("task-30")
        assert task["status"] == TaskStatus.COMPLETED
        assert task["result"] == "done"

    def test_failed_lifecycle(self, task_manager: TaskManager):
        """submitted → working → failed."""
        task_manager.create_task("task-31")
        task_manager.update_task("task-31", status=TaskStatus.WORKING)
        task_manager.update_task("task-31", status=TaskStatus.FAILED, error="boom")

        task = task_manager.get_task("task-31")
        assert task["status"] == TaskStatus.FAILED
        assert task["error"] == "boom"

    def test_canceled_lifecycle(self, task_manager: TaskManager):
        """submitted → working → canceled."""
        task_manager.create_task("task-32")
        task_manager.update_task("task-32", status=TaskStatus.WORKING)
        task_manager.update_task("task-32", status=TaskStatus.CANCELED)

        task = task_manager.get_task("task-32")
        assert task["status"] == TaskStatus.CANCELED


# ------------------------------------------------------------------
# List
# ------------------------------------------------------------------


class TestListTasks:
    def test_list_all(self, task_manager: TaskManager):
        task_manager.create_task("task-40")
        task_manager.create_task("task-41")
        task_manager.create_task("task-42")

        tasks = task_manager.list_tasks()
        ids = {t["id"] for t in tasks}
        assert ids == {"task-40", "task-41", "task-42"}

    def test_list_filtered_by_status(self, task_manager: TaskManager):
        task_manager.create_task("task-43")
        task_manager.update_task("task-43", status=TaskStatus.WORKING)
        task_manager.create_task("task-44")  # still submitted

        working = task_manager.list_tasks(status=TaskStatus.WORKING)
        assert len(working) == 1
        assert working[0]["id"] == "task-43"

        submitted = task_manager.list_tasks(status=TaskStatus.SUBMITTED)
        assert len(submitted) == 1
        assert submitted[0]["id"] == "task-44"

    def test_list_empty(self, task_manager: TaskManager):
        assert task_manager.list_tasks() == []


# ------------------------------------------------------------------
# Cleanup
# ------------------------------------------------------------------


class TestCleanup:
    def test_cleanup_removes_nothing_when_fresh(self, task_manager: TaskManager):
        task_manager.create_task("task-50")
        deleted = task_manager.cleanup_old_tasks(max_age_hours=24)
        assert deleted == 0
        assert task_manager.get_task("task-50") is not None


# ------------------------------------------------------------------
# Persistence across restarts
# ------------------------------------------------------------------


class TestPersistence:
    def test_task_survives_restart(self, tmp_path):
        """Simulate server restart by creating a new TaskManager on the same DB."""
        db_path = tmp_path / "persist_test.db"

        # First instance — create a task
        tm1 = TaskManager(db_path=db_path)
        tm1.create_task("task-60")
        tm1.update_task("task-60", status=TaskStatus.WORKING, debate_id="d-1")

        # Second instance — simulates restart
        tm2 = TaskManager(db_path=db_path)
        task = tm2.get_task("task-60")
        assert task is not None
        assert task["id"] == "task-60"
        assert task["status"] == TaskStatus.WORKING
        assert task["debate_id"] == "d-1"

    def test_multiple_tasks_survive_restart(self, tmp_path):
        db_path = tmp_path / "persist_multi.db"

        tm1 = TaskManager(db_path=db_path)
        tm1.create_task("t1")
        tm1.create_task("t2")
        tm1.update_task("t1", status=TaskStatus.COMPLETED, result="ok")

        tm2 = TaskManager(db_path=db_path)
        tasks = tm2.list_tasks()
        assert len(tasks) == 2
