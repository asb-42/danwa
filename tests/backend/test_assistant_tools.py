"""Tests for Kitsune Agent read-only tools (Phase 1).

Covers:
- Tool registry: registration, definitions, execution
- All 6 read-only tools: get_system_status, list_debates, get_debate_details,
  get_llm_profiles, get_modules, search_knowledge_base
- Error handling: unknown tools, missing context, exceptions
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.assistant_tools import (
    TOOL_REGISTRY,
    execute_tool,
    get_tool_definitions,
)

# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_assistant(sessions=None):
    assistant = MagicMock()
    assistant.list_sessions.return_value = sessions or []
    return assistant


def _make_blueprint_repo(profiles=None):
    repo = MagicMock()
    repo.list_llm_profiles.return_value = profiles or []
    return repo


def _make_debate_store(debates=None):
    store = MagicMock()
    store.list_all.return_value = debates or []
    store.get.return_value = None
    return store


def _make_module_service(modules=None):
    svc = MagicMock()
    svc.discover_local_with_status.return_value = modules or []
    return svc


def _make_knowledge_file(content: str = "") -> Path:
    f = Path(tempfile.mktemp(suffix=".txt"))
    f.write_text(content, encoding="utf-8")
    return f


# ─── Registry ───────────────────────────────────────────────────────────────


class TestToolRegistry:
    def test_registry_has_6_tools(self):
        assert len(TOOL_REGISTRY) >= 6

    def test_get_tool_definitions_format(self):
        defs = get_tool_definitions()
        assert len(defs) >= 6
        for d in defs:
            assert d["type"] == "function"
            assert "name" in d["function"]
            assert "description" in d["function"]
            assert "parameters" in d["function"]

    def test_all_expected_tools_registered(self):
        expected = [
            "get_system_status",
            "list_debates",
            "get_debate_details",
            "get_llm_profiles",
            "get_modules",
            "search_knowledge_base",
        ]
        for name in expected:
            assert name in TOOL_REGISTRY, f"Tool '{name}' not registered"


# ─── execute_tool ───────────────────────────────────────────────────────────


class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        result = await execute_tool("nonexistent_tool", "{}")
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    @pytest.mark.asyncio
    async def test_empty_arguments(self):
        result = await execute_tool("get_system_status", "")
        parsed = json.loads(result)
        assert "active_sessions" in parsed

    @pytest.mark.asyncio
    async def test_invalid_json_arguments(self):
        result = await execute_tool("get_system_status", "not-json")
        parsed = json.loads(result)
        assert "error" in parsed

    @pytest.mark.asyncio
    async def test_tool_exception_caught(self):
        """If a tool raises, execute_tool returns an error dict."""
        # Temporarily register a broken tool
        TOOL_REGISTRY["__test_broken"] = {
            "name": "__test_broken",
            "description": "test",
            "parameters": {},
            "fn": AsyncMock(side_effect=RuntimeError("boom")),
        }
        try:
            result = await execute_tool("__test_broken", "{}")
            parsed = json.loads(result)
            assert "error" in parsed
            assert "boom" in parsed["error"]
        finally:
            del TOOL_REGISTRY["__test_broken"]


# ─── get_system_status ──────────────────────────────────────────────────────


class TestGetSystemStatus:
    @pytest.mark.asyncio
    async def test_returns_counts(self):
        assistant = _make_assistant(sessions=[1, 2, 3])
        repo = _make_blueprint_repo(profiles=[MagicMock(), MagicMock()])
        store = _make_debate_store(debates=[MagicMock()])

        result = await TOOL_REGISTRY["get_system_status"]["fn"](
            assistant_service=assistant,
            blueprint_repository=repo,
            debate_store=store,
        )
        assert result["active_sessions"] == 3
        assert result["llm_profiles_count"] == 2
        assert result["active_debates_count"] == 1

    @pytest.mark.asyncio
    async def test_missing_context_returns_zeros(self):
        result = await TOOL_REGISTRY["get_system_status"]["fn"]()
        assert result["active_sessions"] == 0
        assert result["llm_profiles_count"] == 0
        assert result["active_debates_count"] == 0


# ─── list_debates ───────────────────────────────────────────────────────────


class TestListDebates:
    @pytest.mark.asyncio
    async def test_returns_debates(self):
        debates = [
            {"debate_id": "d1", "title": "AI Ethics", "status": "completed", "current_round": 3, "max_rounds": 5, "created_at": "2026-01-01"},
            {"debate_id": "d2", "title": "Climate", "status": "running", "current_round": 1, "max_rounds": 3, "created_at": "2026-01-02"},
        ]
        store = _make_debate_store(debates=debates)
        result = await TOOL_REGISTRY["list_debates"]["fn"](debate_store=store)
        assert len(result) == 2
        assert result[0]["debate_id"] == "d1"

    @pytest.mark.asyncio
    async def test_filter_by_status(self):
        debates = [
            {"debate_id": "d1", "title": "A", "status": "completed", "current_round": 3, "max_rounds": 5, "created_at": ""},
            {"debate_id": "d2", "title": "B", "status": "running", "current_round": 1, "max_rounds": 3, "created_at": ""},
        ]
        store = _make_debate_store(debates=debates)
        result = await TOOL_REGISTRY["list_debates"]["fn"](status="running", debate_store=store)
        assert len(result) == 1
        assert result[0]["debate_id"] == "d2"

    @pytest.mark.asyncio
    async def test_no_store_returns_error(self):
        result = await TOOL_REGISTRY["list_debates"]["fn"]()
        assert isinstance(result, list)
        assert "error" in result[0]


# ─── get_debate_details ─────────────────────────────────────────────────────


class TestGetDebateDetails:
    @pytest.mark.asyncio
    async def test_returns_details(self):
        debate = {
            "debate_id": "d1",
            "title": "AI Ethics",
            "status": "completed",
            "current_round": 3,
            "max_rounds": 5,
            "final_consensus": 0.85,
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
            "rounds": [{"r": 1}, {"r": 2}, {"r": 3}],
            "llm_assignments": {"strategist": "gpt-4"},
        }
        store = _make_debate_store()
        store.get.return_value = debate

        result = await TOOL_REGISTRY["get_debate_details"]["fn"](debate_id="d1", debate_store=store)
        assert result["debate_id"] == "d1"
        assert result["round_count"] == 3
        assert result["consensus"] == 0.85

    @pytest.mark.asyncio
    async def test_not_found(self):
        store = _make_debate_store()
        store.get.return_value = None
        result = await TOOL_REGISTRY["get_debate_details"]["fn"](debate_id="nonexistent", debate_store=store)
        assert "error" in result

    @pytest.mark.asyncio
    async def test_no_store(self):
        result = await TOOL_REGISTRY["get_debate_details"]["fn"](debate_id="d1")
        assert "error" in result


# ─── get_llm_profiles ───────────────────────────────────────────────────────


class TestGetLlmProfiles:
    @pytest.mark.asyncio
    async def test_returns_profiles(self):
        profiles = [
            SimpleNamespace(id="p1", name="GPT-4", provider="openai", model="gpt-4", service_eligible=True, max_tokens=8192, temperature=0.7),
            SimpleNamespace(id="p2", name="Claude", provider="anthropic", model="claude-3", service_eligible=False, max_tokens=4096, temperature=0.5),
        ]
        repo = _make_blueprint_repo(profiles=profiles)
        result = await TOOL_REGISTRY["get_llm_profiles"]["fn"](blueprint_repository=repo)
        assert len(result) == 2
        assert result[0]["id"] == "p1"
        assert result[1]["provider"] == "anthropic"

    @pytest.mark.asyncio
    async def test_no_repo(self):
        result = await TOOL_REGISTRY["get_llm_profiles"]["fn"]()
        assert isinstance(result, list)
        assert "error" in result[0]


# ─── get_modules ─────────────────────────────────────────────────────────────


class TestGetModules:
    @pytest.mark.asyncio
    async def test_returns_modules(self):
        modules = [
            {"module_id": "m1", "name": "Debate Pack", "version": "1.0", "type": "bundle", "category": "agents", "enabled": True},
            {"module_id": "m2", "name": "Tone Profiles", "version": "1.1", "type": "tone-profiles", "category": "tone-profiles", "enabled": True},
        ]
        svc = _make_module_service(modules=modules)
        result = await TOOL_REGISTRY["get_modules"]["fn"](module_service=svc)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_filter_by_category(self):
        modules = [
            {"module_id": "m1", "name": "A", "version": "1.0", "type": "bundle", "category": "agents", "enabled": True},
            {"module_id": "m2", "name": "B", "version": "1.0", "type": "tone-profiles", "category": "tone-profiles", "enabled": True},
        ]
        svc = _make_module_service(modules=modules)
        result = await TOOL_REGISTRY["get_modules"]["fn"](category="agents", module_service=svc)
        assert len(result) == 1
        assert result[0]["category"] == "agents"

    @pytest.mark.asyncio
    async def test_no_service(self):
        result = await TOOL_REGISTRY["get_modules"]["fn"]()
        assert isinstance(result, list)
        assert "error" in result[0]


# ─── search_knowledge_base ──────────────────────────────────────────────────


class TestSearchKnowledgeBase:
    @pytest.mark.asyncio
    async def test_finds_matches(self):
        kb = _make_knowledge_file("Line 1\nAPI endpoint /health\nLine 3\nLine 4\nhealth check returns 200")
        try:
            result = await TOOL_REGISTRY["search_knowledge_base"]["fn"](query="health", knowledge_base_path=kb)
            assert result["match_count"] >= 2
            assert all("snippet" in m for m in result["matches"])
        finally:
            kb.unlink()

    @pytest.mark.asyncio
    async def test_no_matches(self):
        kb = _make_knowledge_file("Line 1\nLine 2\nLine 3")
        try:
            result = await TOOL_REGISTRY["search_knowledge_base"]["fn"](query="nonexistent", knowledge_base_path=kb)
            assert result["match_count"] == 0
        finally:
            kb.unlink()

    @pytest.mark.asyncio
    async def test_no_knowledge_file(self):
        result = await TOOL_REGISTRY["search_knowledge_base"]["fn"](query="test")
        assert "error" in result

    @pytest.mark.asyncio
    async def test_limit_results(self):
        # Create a file with many matches
        content = "\n".join(["match line"] * 50)
        kb = _make_knowledge_file(content)
        try:
            result = await TOOL_REGISTRY["search_knowledge_base"]["fn"](query="match", knowledge_base_path=kb)
            assert len(result["matches"]) <= 10
        finally:
            kb.unlink()
