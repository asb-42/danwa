"""Tests for backend/services/render_engine.py — engine orchestration and helpers.

Covers:
* :class:`RenderEngineService` lifecycle (submit_job, execute_job)
* Fallback path :meth:`RenderEngineService._build_artifact_from_debate_store`
* Module-level helpers ``_normalize_or_pass``, ``_build_turns_from_node_outputs``,
  ``_debate_to_artifact``
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from backend.models.artifact import DebateArtifact, Turn
from backend.models.render_job import RenderJobStatus
from backend.services.output.base import OutputPlugin
from backend.services.output.registry import PluginRegistry
from backend.services.render_engine import (
    RenderEngineService,
    _build_turns_from_node_outputs,
    _debate_to_artifact,
    _normalize_or_pass,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "render_engine.db"


@pytest.fixture
def artifact_store(db_path: Path):
    from backend.blueprints.migrations import run_migrations
    from backend.services.artifact_store import ArtifactStore

    run_migrations(db_path)
    return ArtifactStore(db_path)


@pytest.fixture
def job_store(db_path: Path):
    from backend.blueprints.migrations import run_migrations
    from backend.services.render_job_store import RenderJobStore

    run_migrations(db_path)
    return RenderJobStore(db_path)


@pytest.fixture
def engine(artifact_store, job_store, tmp_path) -> RenderEngineService:
    return RenderEngineService(
        artifact_store=artifact_store,
        job_store=job_store,
        output_dir=tmp_path / "output",
    )


@pytest.fixture(autouse=True)
def _reset_plugin_registry():
    """Each test gets a clean PluginRegistry singleton."""
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()


class _TinyConfig(BaseModel):
    msg: str = "ok"


class _TinyPlugin(OutputPlugin):
    """Test plugin whose render() returns a fixed list of file paths."""

    plugin_key: str = "tiny"
    plugin_name: str = "Tiny Test Plugin"
    supported_formats: list[str] = ["txt"]
    config_schema: type[BaseModel] = _TinyConfig

    def __init__(self, fail: bool = False, output_name: str = "out.txt") -> None:
        self.fail = fail
        self.output_name = output_name
        self.render_calls: list[dict] = []

    @classmethod
    def validate_config(cls, config: dict) -> BaseModel:
        return _TinyConfig(**config)

    async def render(
        self,
        artifact: DebateArtifact,
        config: BaseModel,
        job_id: str,
        output_dir: Path,
        *,
        progress_callback=None,
    ) -> list[Path]:
        self.render_calls.append(
            {
                "session_id": artifact.session_id,
                "job_id": job_id,
                "output_dir": str(output_dir),
            }
        )
        if progress_callback is not None:
            # Fire a few progress events
            await progress_callback(1, 3)
            await progress_callback(2, 3)
            await progress_callback(3, 3)
        if self.fail:
            raise RuntimeError("plugin boom")
        out_dir = output_dir / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        p = out_dir / self.output_name
        p.write_text("ok", encoding="utf-8")
        return [p]


def _make_artifact(session_id: str = "s1", topic: str = "Test") -> DebateArtifact:
    return DebateArtifact(
        session_id=session_id,
        workflow_id="w1",
        topic=topic,
        transcript=[
            Turn(
                round=1,
                node_id="n1",
                agent_name="A",
                role_type="strategist",
                content="Hello",
            ),
        ],
    )


# ---------------------------------------------------------------------------
# TestSubmitJob
# ---------------------------------------------------------------------------


class TestSubmitJob:
    @pytest.mark.asyncio
    async def test_unknown_plugin_raises_keyerror(self, engine: RenderEngineService) -> None:
        artifact_store = engine.artifact_store
        artifact_store.save(_make_artifact())
        with pytest.raises(KeyError, match="No output plugin registered"):
            await engine.submit_job("s1", "does_not_exist", {})

    @pytest.mark.asyncio
    async def test_invalid_config_raises_valueerror(self, engine: RenderEngineService) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        with pytest.raises(ValueError):
            # missing required field 'msg' if schema enforced
            await engine.submit_job("s1", "tiny", {"msg": "ok"})

    @pytest.mark.asyncio
    async def test_missing_artifact_raises_valueerror(self, engine: RenderEngineService) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        with pytest.raises(ValueError, match="No DebateArtifact found"):
            await engine.submit_job("missing-session", "tiny", {"msg": "ok"})

    @pytest.mark.asyncio
    async def test_happy_path_creates_queued_job(self, engine: RenderEngineService) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        engine.artifact_store.save(_make_artifact())

        job = await engine.submit_job("s1", "tiny", {"msg": "hi"})

        assert job.status == RenderJobStatus.QUEUED
        assert job.plugin_key == "tiny"
        assert job.session_id == "s1"
        assert job.artifact_snapshot_hash != ""
        stored = engine.job_store.get_job(job.id)
        assert stored is not None
        assert stored.status == RenderJobStatus.QUEUED
        # output dir was created
        assert (engine.output_dir / job.id).is_dir()

    @pytest.mark.asyncio
    async def test_config_is_serialized_into_job(self, engine: RenderEngineService) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        engine.artifact_store.save(_make_artifact())

        job = await engine.submit_job("s1", "tiny", {"msg": "serialized"})

        assert job.config == {"msg": "serialized"}


# ---------------------------------------------------------------------------
# TestExecuteJob
# ---------------------------------------------------------------------------


class TestExecuteJob:
    @pytest.mark.asyncio
    async def test_unknown_job_id_logs_and_returns(self, engine: RenderEngineService, caplog) -> None:
        # Just ensure no exception, no state change
        with caplog.at_level("ERROR"):
            await engine.execute_job("does-not-exist")
        assert any("not found" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_happy_path_runs_plugin_and_marks_completed(self, engine: RenderEngineService) -> None:
        plugin_cls = _TinyPlugin
        PluginRegistry.instance().register(plugin_cls)
        engine.artifact_store.save(_make_artifact())
        job = await engine.submit_job("s1", "tiny", {"msg": "ok"})

        await engine.execute_job(job.id)

        stored = engine.job_store.get_job(job.id)
        assert stored is not None
        assert stored.status == RenderJobStatus.COMPLETED
        assert stored.completed_at is not None
        assert stored.started_at is not None
        assert len(stored.output_files) == 1
        assert stored.progress_total == 3
        assert stored.progress_current == 3

    @pytest.mark.asyncio
    async def test_plugin_failure_marks_job_failed(self, engine: RenderEngineService) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        engine.artifact_store.save(_make_artifact())
        job = await engine.submit_job("s1", "tiny", {"msg": "boom"})

        # Patch _TinyPlugin.render to raise by monkeypatching the class
        original_render = _TinyPlugin.render

        async def _bad_render(self, *args, **kwargs):
            self.render_calls.append({"args": args, "kwargs": kwargs})
            raise RuntimeError("explode!")

        _TinyPlugin.render = _bad_render  # type: ignore[assignment]
        try:
            await engine.execute_job(job.id)
        finally:
            _TinyPlugin.render = original_render  # type: ignore[assignment]

        stored = engine.job_store.get_job(job.id)
        assert stored is not None
        assert stored.status == RenderJobStatus.FAILED
        assert stored.error_message == "explode!"
        assert stored.completed_at is not None

    @pytest.mark.asyncio
    async def test_execute_job_artifact_disappeared_raises(self, engine: RenderEngineService, monkeypatch) -> None:
        PluginRegistry.instance().register(_TinyPlugin)
        engine.artifact_store.save(_make_artifact())
        job = await engine.submit_job("s1", "tiny", {"msg": "ok"})

        # Now make the artifact vanish before execute_job reloads it
        monkeypatch.setattr(engine.artifact_store, "get", lambda sid: None)
        # And ensure fallback also returns None
        monkeypatch.setattr(engine, "_build_artifact_from_debate_store", lambda sid: None)

        await engine.execute_job(job.id)

        stored = engine.job_store.get_job(job.id)
        assert stored is not None
        assert stored.status == RenderJobStatus.FAILED
        assert "disappeared" in (stored.error_message or "")


# ---------------------------------------------------------------------------
# TestBuildArtifactFromDebateStore — fallback path
# ---------------------------------------------------------------------------


class TestBuildArtifactFromDebateStore:
    def test_no_fallback_returns_none(self, engine: RenderEngineService, monkeypatch) -> None:
        # Force all stores to look empty
        fake_project_store = MagicMock()
        fake_project_store.list_all.return_value = []
        monkeypatch.setattr("backend.api.deps.get_project_store", lambda: fake_project_store)
        # Global DebateStore is also empty
        fake_debate_store = MagicMock()
        fake_debate_store.get.return_value = None
        fake_debate_store.list_all.return_value = []
        monkeypatch.setattr("backend.persistence.debate_store.DebateStore", lambda *a, **k: fake_debate_store)
        assert engine._build_artifact_from_debate_store("nope") is None

    def test_direct_key_lookup_succeeds(self, engine: RenderEngineService, monkeypatch, tmp_path) -> None:
        # Set up a fake project + debate that matches the session_id directly
        project = MagicMock()
        project.id = "p1"
        proj_dir = tmp_path / "p1"
        proj_dir.mkdir()
        (proj_dir / "debates").mkdir()
        debate_file = proj_dir / "debates" / "s1.json"
        debate_file.write_text(
            json.dumps(
                {
                    "debate_id": "s1",
                    "title": "Direct",
                    "is_mvp": False,
                    "rounds": [
                        {
                            "round": 1,
                            "agent_outputs": [{"role": "strategist", "content": "Hi", "tokens_used": 5}],
                        }
                    ],
                    "request": {"language": "de"},
                }
            )
        )

        fake_project_store = MagicMock()
        fake_project_store.list_all.return_value = [project]
        monkeypatch.setattr("backend.api.deps.get_project_store", lambda: fake_project_store)
        monkeypatch.setattr("backend.api.deps.get_case_dir", lambda pid: proj_dir)

        artifact = engine._build_artifact_from_debate_store("s1")
        assert artifact is not None
        assert artifact.session_id == "s1"
        assert artifact.title == "Direct"
        assert artifact.workflow_id.startswith("debate_")
        # And the artifact was persisted
        assert engine.artifact_store.get("s1") is not None

    def test_fallback_search_by_session_id_field(self, engine: RenderEngineService, monkeypatch, tmp_path) -> None:
        project = MagicMock()
        project.id = "p1"
        proj_dir = tmp_path / "p1"
        proj_dir.mkdir()
        (proj_dir / "debates").mkdir()
        # Debate stored under different key but session_id field matches
        (proj_dir / "debates" / "mvp-1.json").write_text(
            json.dumps(
                {
                    "debate_id": "mvp-1",
                    "session_id": "wf-abc",
                    "title": "BySession",
                    "is_mvp": False,
                    "rounds": [],
                    "request": {"language": "en"},
                }
            )
        )

        fake_project_store = MagicMock()
        fake_project_store.list_all.return_value = [project]
        monkeypatch.setattr("backend.api.deps.get_project_store", lambda: fake_project_store)
        monkeypatch.setattr("backend.api.deps.get_case_dir", lambda pid: proj_dir)

        artifact = engine._build_artifact_from_debate_store("wf-abc")
        assert artifact is not None
        assert artifact.title == "BySession"


# ---------------------------------------------------------------------------
# TestNormalizeOrPass
# ---------------------------------------------------------------------------


class TestNormalizeOrPass:
    def test_plain_text_passes_through(self) -> None:
        assert _normalize_or_pass("Just plain text.", "strategist") == "Just plain text."

    def test_critic_role_normalizes_json(self) -> None:
        # Critic role is one of the normalized roles
        out = _normalize_or_pass(
            json.dumps({"verdict": "approve", "argument": "Looks good"}),
            "critic",
        )
        # Should not be the raw JSON string any more
        assert "verdict" in out or "Looks good" in out


# ---------------------------------------------------------------------------
# TestBuildTurnsFromNodeOutputs
# ---------------------------------------------------------------------------


class TestBuildTurnsFromNodeOutputs:
    def test_empty_returns_empty(self) -> None:
        assert _build_turns_from_node_outputs([]) == []

    def test_skips_system_roles(self) -> None:
        out = _build_turns_from_node_outputs(
            [
                {"role": "complete", "round": 0, "content": "done"},
                {"role": "input", "round": 0, "content": "user query"},
                {"role": "strategist", "round": 1, "content": "Hello"},
            ]
        )
        assert len(out) == 1
        assert out[0].role_type == "strategist"
        assert out[0].round == 1

    def test_uses_role_type_name_from_config(self) -> None:
        out = _build_turns_from_node_outputs(
            [
                {
                    "role": "strategist",
                    "round": 1,
                    "node_id": "n1",
                    "content": "hi",
                    "duration_ms": 50,
                    "tokens_used": 11,
                }
            ],
            node_configs={"n1": {"role_type_name": "Mastermind", "llm_model": "owl"}},
        )
        assert out[0].agent_name == "Mastermind (owl)"
        assert out[0].latency_ms == 50
        assert out[0].token_usage == {"total": 11}

    def test_string_config_is_parsed(self) -> None:
        # node_configs value is a serialized dict string
        cfg = json.dumps({"role_type_name": "Custom", "llm_profile_id": "p1"})
        out = _build_turns_from_node_outputs(
            [
                {
                    "role": "strategist",
                    "round": 1,
                    "node_id": "n1",
                    "content": "hi",
                }
            ],
            node_configs={"n1": cfg},
        )
        # llm_profile_id fallback used for the suffix
        assert "(p1)" in out[0].agent_name

    def test_invalid_string_config_falls_back_to_empty(self) -> None:
        out = _build_turns_from_node_outputs(
            [
                {
                    "role": "strategist",
                    "round": 1,
                    "node_id": "n1",
                    "content": "hi",
                }
            ],
            node_configs={"n1": "not-valid-python{{"},
        )
        # role_type_name falls back to role.title()
        assert out[0].agent_name == "Strategist"

    def test_falls_back_to_llm_assignments(self) -> None:
        out = _build_turns_from_node_outputs(
            [
                {
                    "role": "critic",
                    "round": 1,
                    "node_id": "n1",
                    "content": "hi",
                }
            ],
            llm_assignments={"critic": "critic-profile"},
        )
        assert "critic-profile" in out[0].agent_name

    def test_uses_llm_profile_name_when_no_model(self) -> None:
        out = _build_turns_from_node_outputs(
            [
                {
                    "role": "strategist",
                    "round": 1,
                    "node_id": "n1",
                    "content": "hi",
                }
            ],
            node_configs={"n1": {"llm_profile_name": "Owl-Alpha"}},
        )
        assert "(Owl-Alpha)" in out[0].agent_name

    def test_default_node_id_uses_role_and_round(self) -> None:
        out = _build_turns_from_node_outputs([{"role": "strategist", "round": 2, "content": "hi"}])
        assert out[0].node_id == "strategist_round2"

    def test_role_falls_back_to_node_type(self) -> None:
        out = _build_turns_from_node_outputs([{"node_type": "builder", "round": 1, "content": "hi"}])
        assert out[0].role_type == "builder"


# ---------------------------------------------------------------------------
# TestDebateToArtifact
# ---------------------------------------------------------------------------


class TestDebateToArtifact:
    def test_legacy_rounds_build_turns(self) -> None:
        debate = {
            "debate_id": "d1",
            "title": "Legacy",
            "is_mvp": False,
            "rounds": [
                {
                    "round": 1,
                    "agent_outputs": [{"role": "strategist", "content": "Plan", "tokens_used": 7}],
                },
                {
                    "round": 2,
                    "agent_outputs": [{"role": "critic", "content": "Disagree", "tokens_used": 5}],
                },
            ],
            "result": {"final_consensus": 0.8, "output": "We agree"},
            "request": {"language": "de", "case": {"text": "Case A"}},
        }
        art = _debate_to_artifact(debate)
        assert art.session_id == "d1"
        assert art.workflow_id == "debate_d1"
        assert art.title == "Legacy"
        assert art.topic == "Case A"
        assert art.workflow_name == "debate"
        assert art.consensus_result == {"score": 0.8, "summary": "We agree"}
        assert len(art.transcript) == 2
        # Token usage aggregated
        assert art.metadata["token_usage"]["total"] == 12

    def test_case_text_from_string(self) -> None:
        debate = {
            "debate_id": "d2",
            "is_mvp": False,
            "rounds": [],
            "result": {"consensus": 0.5, "output": ""},
            "request": {"language": "en", "case": "Bare string case"},
        }
        art = _debate_to_artifact(debate)
        assert art.topic == "Bare string case"
        assert art.consensus_result["score"] == 0.5

    def test_consensus_legacy_vs_mvp(self) -> None:
        # Legacy: final_consensus wins
        legacy = {
            "debate_id": "x",
            "is_mvp": False,
            "rounds": [],
            "result": {"final_consensus": 0.9, "consensus": 0.1, "output": ""},
            "request": {"language": "en"},
        }
        assert _debate_to_artifact(legacy).consensus_result["score"] == 0.9

    def test_mvp_debate_uses_snapshot_fallback(self, monkeypatch) -> None:
        # Pretend the snapshot store returns a known state
        fake_snapshot = {
            "state": {
                "node_outputs": [
                    {
                        "role": "strategist",
                        "round": 1,
                        "node_id": "n1",
                        "content": "MVP plan",
                        "duration_ms": 12,
                        "tokens_used": 3,
                    }
                ],
                "node_configs": {"n1": {"role_type_name": "MVP-Strategist"}},
            }
        }

        class _FakeStore:
            def get_latest(self, session_id: str) -> dict | None:
                return fake_snapshot

        monkeypatch.setattr(
            "backend.workflow.state_snapshot.StateSnapshotStore",
            lambda: _FakeStore(),
        )

        debate = {
            "debate_id": "mvp1",
            "session_id": "wf-1",
            "is_mvp": True,
            "rounds": [],
            "llm_assignments": {},
            "result": {"consensus": 0.7, "output": "MVP output"},
            "request": {"language": "de"},
        }
        art = _debate_to_artifact(debate)
        assert len(art.transcript) == 1
        assert art.transcript[0].content == "MVP plan"
        assert art.transcript[0].agent_name == "MVP-Strategist"

    def test_mvp_debate_snapshot_failure_keeps_empty_transcript(self, monkeypatch) -> None:
        class _BrokenStore:
            def get_latest(self, session_id: str):
                raise RuntimeError("disk error")

        monkeypatch.setattr(
            "backend.workflow.state_snapshot.StateSnapshotStore",
            lambda: _BrokenStore(),
        )
        debate = {
            "debate_id": "mvp2",
            "session_id": "wf-2",
            "is_mvp": True,
            "rounds": [],
            "result": {"consensus": 0.4, "output": "out"},
            "request": {"language": "en"},
        }
        art = _debate_to_artifact(debate)
        # No crash, transcript is empty
        assert art.transcript == []
        assert art.consensus_result["score"] == 0.4

    def test_metadata_uses_title_and_language(self) -> None:
        debate = {
            "debate_id": "d3",
            "title": "My Debate",
            "is_mvp": False,
            "rounds": [],
            "result": {},
            "request": {"language": "fr"},
        }
        art = _debate_to_artifact(debate)
        assert art.metadata["title"] == "My Debate"
        assert art.metadata["language"] == "fr"
