"""Tests for InputJob and InputJobStatus."""

from __future__ import annotations

from backend.models.input_job import InputJob, InputJobStatus


class TestInputJobStatus:
    def test_values(self) -> None:
        assert InputJobStatus.QUEUED == "queued"
        assert InputJobStatus.PROCESSING == "processing"
        assert InputJobStatus.COMPLETED == "completed"
        assert InputJobStatus.FAILED == "failed"
        assert InputJobStatus.PENDING_APPROVAL == "pending_approval"


class TestInputJob:
    def test_defaults(self) -> None:
        job = InputJob(plugin_key="standard_text")
        assert job.status == InputJobStatus.QUEUED
        assert job.config == {}
        assert job.raw_input_data == {}
        assert job.processed_input is None
        assert job.error_message is None
        assert job.id  # auto-generated

    def test_with_config(self) -> None:
        job = InputJob(
            plugin_key="stt",
            config={"llm_profile_id": "whisper-large", "stream_partial": True},
        )
        assert job.plugin_key == "stt"
        assert job.config["llm_profile_id"] == "whisper-large"

    def test_status_transitions(self) -> None:
        job = InputJob(plugin_key="standard_text")
        assert job.status == InputJobStatus.QUEUED
        job.status = InputJobStatus.PROCESSING
        assert job.status == InputJobStatus.PROCESSING
        job.status = InputJobStatus.COMPLETED
        assert job.status == InputJobStatus.COMPLETED

    def test_failed_status(self) -> None:
        job = InputJob(plugin_key="stt")
        job.status = InputJobStatus.FAILED
        job.error_message = "STT service unavailable"
        assert job.status == InputJobStatus.FAILED
        assert job.error_message == "STT service unavailable"

    def test_pending_approval(self) -> None:
        job = InputJob(plugin_key="a2a_inbound")
        job.status = InputJobStatus.PENDING_APPROVAL
        assert job.status == InputJobStatus.PENDING_APPROVAL
