"""Tests for RenderJob and RenderJobStatus."""

from __future__ import annotations

from backend.models.render_job import RenderJob, RenderJobStatus


class TestRenderJobStatus:
    def test_values(self) -> None:
        assert RenderJobStatus.QUEUED == "queued"
        assert RenderJobStatus.RUNNING == "running"
        assert RenderJobStatus.COMPLETED == "completed"
        assert RenderJobStatus.FAILED == "failed"


class TestRenderJob:
    def test_defaults(self) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        assert job.status == RenderJobStatus.QUEUED
        assert job.config == {}
        assert job.output_files == []
        assert job.error_message is None
        assert job.id  # auto-generated

    def test_with_config(self) -> None:
        job = RenderJob(
            session_id="s1",
            plugin_key="tts",
            config={"voice_mapping": {"Alice": "de-DE-ConradNeural"}},
        )
        assert job.plugin_key == "tts"
        assert job.config["voice_mapping"]["Alice"] == "de-DE-ConradNeural"

    def test_status_transitions(self) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        assert job.status == RenderJobStatus.QUEUED
        job.status = RenderJobStatus.RUNNING
        assert job.status == RenderJobStatus.RUNNING
        job.status = RenderJobStatus.COMPLETED
        assert job.status == RenderJobStatus.COMPLETED

    def test_failed_status(self) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        job.status = RenderJobStatus.FAILED
        job.error_message = "Something went wrong"
        assert job.status == RenderJobStatus.FAILED
        assert job.error_message == "Something went wrong"
