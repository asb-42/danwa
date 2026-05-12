"""Tests for ArtifactStore, RenderJobStore, and RenderEngineService."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.models.artifact import DebateArtifact, Turn
from backend.models.render_job import RenderJob, RenderJobStatus
from backend.services.artifact_store import ArtifactStore
from backend.services.render_job_store import RenderJobStore

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "test.db"


@pytest.fixture
def artifact_store(db_path: Path) -> ArtifactStore:
    from backend.blueprints.migrations import run_migrations

    run_migrations(db_path)
    return ArtifactStore(db_path)


@pytest.fixture
def job_store(db_path: Path) -> RenderJobStore:
    from backend.blueprints.migrations import run_migrations

    run_migrations(db_path)
    return RenderJobStore(db_path)


def _make_artifact(session_id: str = "s1") -> DebateArtifact:
    return DebateArtifact(
        session_id=session_id,
        workflow_id="w1",
        topic="Test",
        transcript=[
            Turn(round=1, node_id="n1", agent_name="A", role_type="strategist", content="Hello"),
        ],
    )


# ---------------------------------------------------------------------------
# ArtifactStore Tests
# ---------------------------------------------------------------------------


class TestArtifactStore:
    def test_save_and_get(self, artifact_store: ArtifactStore) -> None:
        a = _make_artifact()
        artifact_store.save(a)
        loaded = artifact_store.get("s1")
        assert loaded is not None
        assert loaded.session_id == "s1"
        assert loaded.topic == "Test"
        assert len(loaded.transcript) == 1

    def test_get_nonexistent(self, artifact_store: ArtifactStore) -> None:
        assert artifact_store.get("nonexistent") is None

    def test_exists(self, artifact_store: ArtifactStore) -> None:
        assert not artifact_store.exists("s1")
        artifact_store.save(_make_artifact())
        assert artifact_store.exists("s1")

    def test_delete(self, artifact_store: ArtifactStore) -> None:
        artifact_store.save(_make_artifact())
        assert artifact_store.exists("s1")
        artifact_store.delete("s1")
        assert not artifact_store.exists("s1")

    def test_overwrite(self, artifact_store: ArtifactStore) -> None:
        a1 = _make_artifact()
        artifact_store.save(a1)
        a2 = _make_artifact()
        a2.topic = "Updated Topic"
        artifact_store.save(a2)
        loaded = artifact_store.get("s1")
        assert loaded is not None
        assert loaded.topic == "Updated Topic"


# ---------------------------------------------------------------------------
# RenderJobStore Tests
# ---------------------------------------------------------------------------


class TestRenderJobStore:
    def test_create_and_get(self, job_store: RenderJobStore) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        job_store.create_job(job)
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.session_id == "s1"
        assert loaded.plugin_key == "print"
        assert loaded.status == RenderJobStatus.QUEUED

    def test_get_nonexistent(self, job_store: RenderJobStore) -> None:
        assert job_store.get_job("nonexistent") is None

    def test_update_status(self, job_store: RenderJobStore) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        job_store.create_job(job)
        job_store.update_job(job.id, status=RenderJobStatus.RUNNING)
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.status == RenderJobStatus.RUNNING

    def test_update_output_files(self, job_store: RenderJobStore) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        job_store.create_job(job)
        job_store.update_job(
            job.id,
            status=RenderJobStatus.COMPLETED,
            output_files=["/data/outputs/j1/debate.pdf"],
        )
        loaded = job_store.get_job(job.id)
        assert loaded is not None
        assert loaded.output_files == ["/data/outputs/j1/debate.pdf"]

    def test_list_jobs(self, job_store: RenderJobStore) -> None:
        for i in range(3):
            job_store.create_job(RenderJob(session_id=f"s{i}", plugin_key="print"))
        jobs = job_store.list_jobs()
        assert len(jobs) == 3

    def test_list_filter_session(self, job_store: RenderJobStore) -> None:
        job_store.create_job(RenderJob(session_id="s1", plugin_key="print"))
        job_store.create_job(RenderJob(session_id="s2", plugin_key="tts"))
        s1_jobs = job_store.list_jobs(session_id="s1")
        assert len(s1_jobs) == 1
        assert s1_jobs[0].session_id == "s1"

    def test_delete_job(self, job_store: RenderJobStore) -> None:
        job = RenderJob(session_id="s1", plugin_key="print")
        job_store.create_job(job)
        assert job_store.get_job(job.id) is not None
        job_store.delete_job(job.id)
        assert job_store.get_job(job.id) is None
