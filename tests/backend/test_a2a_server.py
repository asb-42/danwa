"""Tests for A2A Server — task creation, polling, cancellation."""

from __future__ import annotations

import pytest

from backend.a2a.schemas import A2AMessage, A2ATask, A2ATextPart
from backend.a2a.server import A2AServer
from backend.a2a.task_manager import TaskManager, TaskStatus


@pytest.fixture()
def task_manager(tmp_path) -> TaskManager:
    """Isolated TaskManager with a temporary database."""
    return TaskManager(db_path=tmp_path / "test_a2a_tasks.db")


@pytest.fixture()
def server(task_manager: TaskManager) -> A2AServer:
    """A2AServer with isolated TaskManager."""
    return A2AServer(task_manager=task_manager, project_id="test-project")


# ------------------------------------------------------------------
# handle_task_send
# ------------------------------------------------------------------


class TestHandleTaskSend:
    @pytest.mark.asyncio
    async def test_send_creates_task(self, server: A2AServer, task_manager: TaskManager):
        task = A2ATask(
            id="send-1",
            message=A2AMessage(
                role="user",
                parts=[A2ATextPart(type="text", text="What is AI?")],
            ),
        )
        result = await server.handle_task_send(task)

        assert result["id"] == "send-1"
        assert result["status"]["state"] == TaskStatus.SUBMITTED.value

        # Verify task was persisted
        stored = task_manager.get_task("send-1")
        assert stored is not None
        assert stored["status"] == TaskStatus.SUBMITTED

    @pytest.mark.asyncio
    async def test_send_generates_id_when_missing(self, server: A2AServer):
        task = A2ATask(
            message=A2AMessage(
                role="user",
                parts=[A2ATextPart(type="text", text="Hello")],
            ),
        )
        result = await server.handle_task_send(task)

        assert result["id"] is not None
        assert len(result["id"]) > 0
        assert result["status"]["state"] == TaskStatus.SUBMITTED.value

    @pytest.mark.asyncio
    async def test_send_returns_error_when_no_text(self, server: A2AServer):
        task = A2ATask(id="no-text", message=A2AMessage(role="user", parts=[]))
        result = await server.handle_task_send(task)

        assert result["id"] == "no-text"
        assert result["status"]["state"] == "failed"
        assert "No text content" in result["status"]["message"]

    @pytest.mark.asyncio
    async def test_send_returns_error_when_message_is_none(self, server: A2AServer):
        task = A2ATask(id="no-msg", message=None)
        result = await server.handle_task_send(task)

        assert result["id"] == "no-msg"
        assert result["status"]["state"] == "failed"


# ------------------------------------------------------------------
# handle_task_get
# ------------------------------------------------------------------


class TestHandleTaskGet:
    @pytest.mark.asyncio
    async def test_get_submitted_task(self, server: A2AServer, task_manager: TaskManager):
        task_manager.create_task("get-1", status=TaskStatus.SUBMITTED)
        result = await server.handle_task_get("get-1")

        assert result["id"] == "get-1"
        assert result["status"]["state"] == TaskStatus.SUBMITTED.value

    @pytest.mark.asyncio
    async def test_get_completed_task_with_result(self, server: A2AServer, task_manager: TaskManager):
        task_manager.create_task("get-2", status=TaskStatus.COMPLETED)
        task_manager.update_task("get-2", result="The debate concluded with consensus.")

        result = await server.handle_task_get("get-2")

        assert result["id"] == "get-2"
        assert result["status"]["state"] == TaskStatus.COMPLETED.value
        assert "artifacts" in result
        assert len(result["artifacts"]) == 1
        assert result["artifacts"][0]["parts"][0]["text"] == "The debate concluded with consensus."

    @pytest.mark.asyncio
    async def test_get_failed_task_with_error(self, server: A2AServer, task_manager: TaskManager):
        task_manager.create_task("get-3", status=TaskStatus.FAILED)
        task_manager.update_task("get-3", error="LLM timeout")

        result = await server.handle_task_get("get-3")

        assert result["id"] == "get-3"
        assert result["status"]["state"] == TaskStatus.FAILED.value
        assert result["status"]["message"] == "LLM timeout"

    @pytest.mark.asyncio
    async def test_get_nonexistent_task(self, server: A2AServer):
        result = await server.handle_task_get("nonexistent")

        assert result["id"] == "nonexistent"
        assert result["status"]["state"] == "failed"
        assert "not found" in result["status"]["message"].lower()


# ------------------------------------------------------------------
# handle_task_cancel
# ------------------------------------------------------------------


class TestHandleTaskCancel:
    @pytest.mark.asyncio
    async def test_cancel_submitted_task(self, server: A2AServer, task_manager: TaskManager):
        task_manager.create_task("cancel-1", status=TaskStatus.SUBMITTED)
        result = await server.handle_task_cancel("cancel-1")

        assert result["id"] == "cancel-1"
        assert result["status"]["state"] == TaskStatus.CANCELED.value

        # Verify persisted
        stored = task_manager.get_task("cancel-1")
        assert stored["status"] == TaskStatus.CANCELED

    @pytest.mark.asyncio
    async def test_cancel_working_task(self, server: A2AServer, task_manager: TaskManager):
        task_manager.create_task("cancel-2", status=TaskStatus.WORKING)
        result = await server.handle_task_cancel("cancel-2")

        assert result["status"]["state"] == TaskStatus.CANCELED.value

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_task(self, server: A2AServer):
        result = await server.handle_task_cancel("nonexistent")

        assert result["id"] == "nonexistent"
        assert result["status"]["state"] == "failed"


# ------------------------------------------------------------------
# Helper methods
# ------------------------------------------------------------------


class TestHelpers:
    def test_extract_topic_from_message(self):
        msg = A2AMessage(
            role="user",
            parts=[A2ATextPart(type="text", text="Debate topic here")],
        )
        topic = A2AServer._extract_topic(msg)
        assert topic == "Debate topic here"

    def test_extract_topic_returns_none_for_empty(self):
        assert A2AServer._extract_topic(None) is None
        assert A2AServer._extract_topic(A2AMessage(parts=[])) is None

    def test_extract_topic_skips_non_text_parts(self):
        msg = A2AMessage(
            parts=[
                A2ATextPart(type="image", text=""),
                A2ATextPart(type="text", text="Actual topic"),
            ]
        )
        assert A2AServer._extract_topic(msg) == "Actual topic"

    def test_format_debate_result(self):
        result = {
            "final_consensus": 0.85,
            "current_round": 3,
            "output": "The debate concluded successfully.",
            "agent_outputs": [
                {"role": "critic", "content": "Critical analysis here."},
                {"role": "optimizer", "content": "Optimization suggestions."},
            ],
        }
        formatted = A2AServer._format_debate_result(result)

        assert "85.0%" in formatted
        assert "Rounds: 3" in formatted
        assert "The debate concluded successfully." in formatted
        assert "Critic" in formatted
        assert "Optimizer" in formatted

    def test_format_debate_result_empty(self):
        result = {}
        formatted = A2AServer._format_debate_result(result)
        assert "0.0%" in formatted
        assert "No output generated." in formatted

    def test_error_response_format(self):
        resp = A2AServer._error_response("task-x", "Something went wrong")
        assert resp["id"] == "task-x"
        assert resp["status"]["state"] == "failed"
        assert resp["status"]["message"] == "Something went wrong"
