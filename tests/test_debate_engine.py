import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
from src.core.debate_engine import DebateEngine, DebateState
from src.core.trace_logger import TraceLogger
import tempfile


@pytest.fixture
def engine():
    with patch("src.core.debate_engine.LLMRouter") as mock_router_cls, \
         patch("src.core.debate_engine.WebSearchTool") as mock_search_cls, \
         patch("src.core.debate_engine.DebateMemory") as mock_memory_cls, \
         patch("src.core.debate_engine.PrivacyGuard") as mock_privacy_cls, \
         patch("src.core.debate_engine.PromptManager") as mock_pm_cls, \
         patch("src.core.debate_engine.yaml.safe_load") as mock_yaml_load:

        # Mock settings.yaml content
        mock_yaml_load.return_value = {
            "search": {
                "engine": "duckduckgo",
                "url": "",
                "max_results": 5
            },
            "privacy": {
                "strict_mode": False,
                "retention_days": 90
            },
            "agent_profiles": {
                "profiles": {}
            }
        }

        mock_router = MagicMock()
        mock_router.call = AsyncMock()
        mock_router_cls.return_value = mock_router

        mock_pm = MagicMock()
        mock_pm.assign_variant.return_value = "A"
        mock_pm.get.return_value = {
            "content": "Du bist {role}.",
            "version": "v1.0",
            "hash": "abc123",
            "mtime": 123.0,
            "path": "config/prompts/strategist.md"
        }
        mock_pm_cls.return_value = mock_pm

        mock_privacy = MagicMock()
        mock_privacy.redact_traces = False
        mock_privacy_cls.return_value = mock_privacy

        engine = DebateEngine(
            profile_name="local_lm_studio",
            max_rounds=3,
            threshold=0.75,
            enable_fact_check=False,
            enable_memory=False
        )
        engine.router = mock_router
        engine.prompt_mgr = mock_pm
        engine.privacy = mock_privacy

        with tempfile.TemporaryDirectory() as tmpdir:
            engine.logger = TraceLogger("test_session")
            yield engine


@pytest.fixture
def mock_llm_response():
    def _make(content="Test response", tokens=100, model="test-model"):
        return {
            "content": content,
            "tokens_used": tokens,
            "model": model,
            "finish_reason": "stop"
        }
    return _make


@pytest.mark.asyncio
async def test_debate_state_defaults():
    state = DebateState()
    assert state.session_id is not None
    assert len(state.session_id) == 8
    assert state.context == ""
    assert state.rounds == []
    assert state.final_consensus == 0.0
    assert state.output == ""
    assert state.validation_report == []
    assert isinstance(state.created_at, object)


@pytest.mark.asyncio
async def test_debate_runs_to_completion(engine, mock_llm_response):
    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.95", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Test response", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic")

    assert state.final_consensus == 0.95
    assert len(state.rounds) >= 1
    assert state.output != ""
    assert state.used_variant == "A"


@pytest.mark.asyncio
async def test_debate_stops_early_on_consensus(engine):
    call_count = 0

    async def moderator_high_consensus(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = moderator_high_consensus

    state = await engine.run("Test topic", progress_callback=None)

    assert state.final_consensus >= 0.75
    assert len(state.rounds) <= engine.max_rounds


@pytest.mark.asyncio
async def test_debate_runs_max_rounds(engine):
    async def low_consensus(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.50", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = low_consensus

    state = await engine.run("Test topic")

    assert len(state.rounds) == engine.max_rounds


@pytest.mark.asyncio
async def test_debate_with_fact_check(engine, mock_llm_response):
    engine.search_tool = MagicMock()
    engine.search_tool.search = AsyncMock(return_value=[
        {"title": "Source 1", "url": "http://example.com", "snippet": "Evidence"}
    ])

    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return mock_llm_response()

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic with claims")

    assert state.validation_report is not None


@pytest.mark.asyncio
async def test_debate_extract_claims(engine):
    engine.router.call = AsyncMock(return_value={
        "content": '["Claim 1", "Claim 2", "Claim 3"]',
        "tokens_used": 50,
        "model": "test",
        "finish_reason": "stop"
    })

    claims = await engine._extract_claims("Test draft")

    assert isinstance(claims, list)
    assert len(claims) <= 3


@pytest.mark.asyncio
async def test_debate_fact_check_validation(engine):
    engine.search_tool = MagicMock()
    engine.search_tool.search = AsyncMock(return_value=[
        {"title": "Test", "url": "http://test.com", "snippet": "Info"}
    ])

    # Mock _extract_claims to avoid calling the router
    engine._extract_claims = AsyncMock(return_value=["Test claim"])

    validation = await engine._run_search_validation("Test claim here")

    assert isinstance(validation, list)
    if validation:
        assert "claim" in validation[0]
        assert "evidence" in validation[0]


@pytest.mark.asyncio
async def test_debate_memory_injection(engine):
    mock_memory = MagicMock()
    mock_memory.search_precedents.return_value = [
        {
            "document": "Relevant precedent text",
            "metadata": {"consensus": 0.85},
            "relevance_score": 0.95
        }
    ]
    engine.memory = mock_memory

    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.90", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic with memory")

    assert state.precedents_retrieved is not None
    mock_memory.search_precedents.assert_called_once()


@pytest.mark.asyncio
async def test_debate_moderator_invalid_response(engine):
    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "invalid text", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic")

    assert state.final_consensus == 0.5


@pytest.mark.asyncio
async def test_debate_with_progress_callback(engine):
    progress_calls = []

    async def progress_callback(step, detail):
        progress_calls.append((step, detail))

    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    await engine.run("Test topic", progress_callback=progress_callback)

    assert len(progress_calls) > 0
    assert any("round" in call[0].lower() or "agent" in call[0].lower() for call in progress_calls)


@pytest.mark.asyncio
async def test_debate_strict_mode_blocks_external(engine):
    engine.privacy.strict_mode = True
    engine.search_tool = MagicMock()

    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    await engine.run("Test topic")

    assert engine.search_tool is None


@pytest.mark.asyncio
async def test_debate_variant_override(engine):
    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic", variant_override="B")

    assert state.used_variant == "B"
    engine.prompt_mgr.get.assert_called()


@pytest.mark.asyncio
async def test_debate_trace_logger_writes(engine):
    async def side_effect(*args, **kwargs):
        system_prompt = args[0] if args else kwargs.get("system_prompt", "")
        user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
        if "Moderator" in system_prompt or "Rate consensus" in user_prompt:
            return {"content": "0.85", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
        return {"content": "Draft", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

    engine.router.call.side_effect = side_effect

    state = await engine.run("Test topic")

    log = engine.logger.get_session_log()
    assert len(log) > 0
    assert all("step" in entry and "agent" in entry for entry in log)
