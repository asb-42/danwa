"""Tests for InputComposerService, InputJobStore, and InputStore."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.debate_input import DebateInput
from backend.models.input_job import InputJob, InputJobStatus
from backend.services.input.input_engine import InputComposerService
from backend.services.input.input_job_store import InputJobStore
from backend.services.input.input_store import InputStore


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def job_store(db_path: Path) -> InputJobStore:
    from backend.blueprints.migrations import run_migrations

    run_migrations(db_path)
    return InputJobStore(db_path)


@pytest.fixture
def input_store(db_path: Path) -> InputStore:
    from backend.blueprints.migrations import run_migrations

    run_migrations(db_path)
    return InputStore(db_path)


@pytest.fixture(autouse=True)
def _ensure_plugins():
    """Ensure plugins are registered (idempotent import)."""
    import backend.services.input.plugins  # noqa: F401

    yield


# ---------------------------------------------------------------------------
# InputJobStore Tests
# ---------------------------------------------------------------------------


class TestInputJobStore:
    def test_create_and_get(self, job_store: InputJobStore) -> None:
        job = InputJob(plugin_key="standard_text")
        job_store.create_job(job)
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.plugin_key == "standard_text"
        assert loaded.status == InputJobStatus.QUEUED

    def test_get_nonexistent(self, job_store: InputJobStore) -> None:
        assert job_store.get_job("nonexistent") is None

    def test_update_status(self, job_store: InputJobStore) -> None:
        job = InputJob(plugin_key="standard_text")
        job_store.create_job(job)
        job_store.update_job(job.id, status=InputJobStatus.PROCESSING)
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.status == InputJobStatus.PROCESSING

    def test_update_with_processed_input(self, job_store: InputJobStore) -> None:
        job = InputJob(plugin_key="standard_text")
        job_store.create_job(job)
        debate_input = DebateInput(
            source_plugin_key="standard_text",
            topic="Test topic",
        )
        job_store.update_job(
            job.id,
            status=InputJobStatus.COMPLETED,
            processed_input=debate_input,
        )
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.status == InputJobStatus.COMPLETED
        assert loaded.processed_input is not None
        assert loaded.processed_input.topic == "Test topic"

    def test_list_jobs(self, job_store: InputJobStore) -> None:
        for i in range(3):
            job_store.create_job(InputJob(plugin_key="standard_text"))
        jobs = job_store.list_jobs()
        assert len(jobs) == 3

    def test_list_filter_plugin(self, job_store: InputJobStore) -> None:
        job_store.create_job(InputJob(plugin_key="standard_text"))
        job_store.create_job(InputJob(plugin_key="stt"))
        text_jobs = job_store.list_jobs(plugin_key="standard_text")
        assert len(text_jobs) == 1

    def test_delete_job(self, job_store: InputJobStore) -> None:
        job = InputJob(plugin_key="standard_text")
        job_store.create_job(job)
        assert job_store.get_job(job.id) is not None
        job_store.delete_job(job.id)
        assert job_store.get_job(job.id) is None


# ---------------------------------------------------------------------------
# InputStore Tests
# ---------------------------------------------------------------------------


class TestInputStore:
    def test_save_and_get(self, input_store: InputStore) -> None:
        d = DebateInput(source_plugin_key="standard_text", topic="Test")
        d.session_id = "s1"
        input_store.save(d)
        loaded = input_store.get("s1")
        assert loaded is not None
        assert loaded.topic == "Test"

    def test_get_nonexistent(self, input_store: InputStore) -> None:
        assert input_store.get("nonexistent") is None

    def test_exists(self, input_store: InputStore) -> None:
        assert not input_store.exists("s1")
        d = DebateInput(source_plugin_key="standard_text", topic="Test")
        d = d.model_copy(update={"session_id": "s1"})
        input_store.save(d)
        assert input_store.exists("s1")

    def test_delete(self, input_store: InputStore) -> None:
        d = DebateInput(source_plugin_key="standard_text", topic="Test")
        d = d.model_copy(update={"session_id": "s1"})
        input_store.save(d)
        input_store.delete("s1")
        assert not input_store.exists("s1")


# ---------------------------------------------------------------------------
# InputComposerService Tests
# ---------------------------------------------------------------------------


class TestInputComposerService:
    @pytest.fixture
    def engine(self, job_store: InputJobStore) -> InputComposerService:
        return InputComposerService(job_store=job_store)

    async def test_submit_standard_text(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("standard_text", {}, {"topic": "Test debate"})
        assert job.status == InputJobStatus.COMPLETED
        assert job.processed_input is not None
        assert job.processed_input.topic == "Test debate"

    async def test_submit_stt_creates_processing_job(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("stt", {"llm_profile_id": "whisper-1"}, {})
        assert job.status == InputJobStatus.PROCESSING

    async def test_submit_a2a_with_approval(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("a2a_inbound", {"require_approval": True}, {"topic": "From agent"})
        assert job.status == InputJobStatus.PENDING_APPROVAL

    async def test_submit_unknown_plugin(self, engine: InputComposerService) -> None:
        with pytest.raises(KeyError):
            await engine.submit_input("nonexistent", {}, {})

    async def test_approve_a2a(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("a2a_inbound", {"require_approval": True}, {})
        assert job.status == InputJobStatus.PENDING_APPROVAL
        updated = await engine.approve_a2a(job.id)
        assert updated is not None
        assert updated.status == InputJobStatus.PROCESSING

    async def test_reject_a2a(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("a2a_inbound", {"require_approval": True}, {})
        updated = await engine.reject_a2a(job.id)
        assert updated is not None
        assert updated.status == InputJobStatus.FAILED

    async def test_finalize_input(self, engine: InputComposerService) -> None:
        job = await engine.submit_input("stt", {"llm_profile_id": "whisper-1"}, {})
        debate_input = DebateInput(
            source_plugin_key="stt",
            topic="Transcribed text",
        )
        await engine.finalize_input(job.id, debate_input)
        updated = engine.job_store.get_job(job.id)
        assert updated is not None
        assert updated.status == InputJobStatus.COMPLETED
        assert updated.processed_input.topic == "Transcribed text"
