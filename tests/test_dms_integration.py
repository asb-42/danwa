import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.core.debate_engine import DebateEngine
from src.dms.dms import DMS
from src.dms.rag_context_formatter import RAGContextFormatter


@pytest.fixture
def rag_formatter():
    return RAGContextFormatter()


@pytest.fixture
def mock_dms_with_chunks():
    with patch("src.ui.chainlit_app.DMS") as mock_dms_cls:
        instance = MagicMock()
        instance.auto_retrieve_for_topic.return_value = [
            {"text": "Climate change is real", "metadata": {"file_name": "climate.pdf", "chunk_index": 0}},
            {"text": "Global warming effects", "metadata": {"file_name": "effects.pdf", "chunk_index": 1}}
        ]
        instance.get_rag_context.return_value = [
            {"text": "Manual context chunk", "metadata": {"file_name": "manual.pdf", "chunk_index": 0}}
        ]
        instance.list_projects.return_value = [{"id": "proj1", "name": "Test Project"}]
        instance.list_documents.return_value = [{"id": "doc1", "filename": "test.pdf"}]
        mock_dms_cls.return_value = instance
        yield instance


@pytest.fixture
def engine_with_dms_rag(mock_dms_with_chunks):
    with patch("src.core.debate_engine.LLMRouter") as mock_router_cls, \
         patch("src.core.debate_engine.WebSearchTool"), \
         patch("src.core.debate_engine.DebateMemory"), \
         patch("src.core.debate_engine.PrivacyGuard") as mock_privacy_cls, \
         patch("src.core.debate_engine.PromptManager") as mock_pm_cls:

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

        dms = mock_dms_with_chunks
        chunks = dms.auto_retrieve_for_topic("climate change", project_id="proj1")
        formatted_rag = RAGContextFormatter().format(chunks)

        engine = DebateEngine(
            profile_name="local_lm_studio",
            max_rounds=1,
            threshold=0.75,
            enable_fact_check=False,
            enable_memory=False,
            rag_context=formatted_rag
        )
        engine.router = mock_router
        engine.prompt_mgr = mock_pm
        engine.privacy = mock_privacy
        yield engine


class TestDMSToDebateEngineIntegration:
    @pytest.mark.asyncio
    async def test_rag_context_from_dms_passed_to_engine(self, engine_with_dms_rag):
        async def mock_llm(*args, **kwargs):
            prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            if "Moderator" in args[0] or "Bewert" in prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return {"content": "Test response", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

        engine_with_dms_rag.router.call = AsyncMock(side_effect=mock_llm)
        state = await engine_with_dms_rag.run("climate change debate")

        assert "## RAG Context" in state.context
        assert "climate.pdf" in state.context
        assert "effects.pdf" in state.context

    @pytest.mark.asyncio
    async def test_dms_document_chunks_in_debate_output(self, engine_with_dms_rag):
        async def mock_llm(*args, **kwargs):
            prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            if "Moderator" in args[0] or "Bewert" in prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return {"content": "Test response", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

        engine_with_dms_rag.router.call = AsyncMock(side_effect=mock_llm)
        state = await engine_with_dms_rag.run("climate change debate")

        assert "[Document 1 from climate.pdf]" in state.context
        assert "[Document 2 from effects.pdf]" in state.context

    @pytest.mark.asyncio
    async def test_manual_rag_context_from_dms_in_debate(self, mock_dms_with_chunks):
        with patch("src.core.debate_engine.LLMRouter") as mock_router_cls, \
             patch("src.core.debate_engine.WebSearchTool"), \
             patch("src.core.debate_engine.DebateMemory"), \
             patch("src.core.debate_engine.PrivacyGuard") as mock_privacy_cls, \
             patch("src.core.debate_engine.PromptManager") as mock_pm_cls:

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

            dms = mock_dms_with_chunks
            manual_chunks = dms.get_rag_context("session1")
            formatted_rag = RAGContextFormatter().format(manual_chunks)

            engine = DebateEngine(
                profile_name="local_lm_studio",
                max_rounds=1,
                threshold=0.75,
                enable_fact_check=False,
                enable_memory=False,
                rag_context=formatted_rag
            )
            engine.router = mock_router
            engine.prompt_mgr = mock_pm
            engine.privacy = mock_privacy

            async def mock_llm(*args, **kwargs):
                prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
                if "Moderator" in args[0] or "Bewert" in prompt:
                    return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
                return {"content": "Test response", "tokens_used": 100, "model": "test", "finish_reason": "stop"}

            engine.router.call = AsyncMock(side_effect=mock_llm)
            state = await engine.run("manual context debate")

            assert "manual.pdf" in state.context
            assert "[Document 1 from manual.pdf]" in state.context
