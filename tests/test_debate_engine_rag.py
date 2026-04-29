import pytest
from unittest.mock import AsyncMock, patch, MagicMock, call
from pathlib import Path
import tempfile
from src.core.debate_engine import DebateEngine, DebateState
from src.core.trace_logger import TraceLogger
from src.dms.dms import DMS
from src.dms.rag_context_formatter import RAGContextFormatter
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

with patch("chainlit.ChatSettings") as mock_settings, \
     patch("chainlit.Action") as mock_action, \
     patch("chainlit.Message") as mock_message, \
     patch("chainlit.user_session") as mock_session, \
     patch("chainlit.action_callback", lambda f: f):
    mock_settings.return_value.send = AsyncMock()
    mock_action.return_value = MagicMock()
    mock_message.return_value.send = AsyncMock()
    from src.ui import chainlit_app


@pytest.fixture
def rag_formatter():
    return RAGContextFormatter()


@pytest.fixture
def engine_with_rag():
    with patch("src.core.debate_engine.LLMRouter") as mock_router_cls, \
         patch("src.core.debate_engine.WebSearchTool") as mock_search_cls, \
         patch("src.core.debate_engine.DebateMemory") as mock_memory_cls, \
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

        engine = DebateEngine(
            profile_name="local_lm_studio",
            max_rounds=3,
            threshold=0.75,
            enable_fact_check=False,
            enable_memory=False,
            rag_context="Test RAG Context"
        )
        engine.router = mock_router
        engine.prompt_mgr = mock_pm
        engine.privacy = mock_privacy

        with tempfile.TemporaryDirectory() as tmpdir:
            engine.logger = TraceLogger("test_session")
            yield engine


@pytest.fixture
def engine_without_rag():
    with patch("src.core.debate_engine.LLMRouter") as mock_router_cls, \
         patch("src.core.debate_engine.WebSearchTool") as mock_search_cls, \
         patch("src.core.debate_engine.DebateMemory") as mock_memory_cls, \
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

        engine = DebateEngine(
            profile_name="local_lm_studio",
            max_rounds=3,
            threshold=0.75,
            enable_fact_check=False,
            enable_memory=False,
            rag_context=None
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


@pytest.fixture
def mock_dms():
    with patch("src.ui.chainlit_app.DMS") as mock_dms_class:
        instance = MagicMock()
        instance.list_projects.return_value = [
            {"id": "proj1", "name": "Test Project", "description": ""}
        ]
        instance.list_documents.return_value = [
            {"id": "doc1", "filename": "test.pdf", "project_id": "proj1"}
        ]
        instance.auto_retrieve_for_topic.return_value = [
            {"text": "RAG chunk 1", "source": "test.pdf", "chunk_index": 0, "project_id": "proj1"}
        ]
        instance.get_rag_context.return_value = [
            {"text": "RAG chunk 1", "metadata": {"file_name": "test.pdf", "chunk_index": 0}}
        ]
        mock_dms_class.return_value = instance
        yield instance


@pytest.fixture
def mock_chainlit_message():
    msg = MagicMock()
    msg.content = "Test debate topic about climate change"
    msg.elements = []
    return msg


@pytest.fixture
def mock_chainlit_session():
    session = MagicMock()
    session.get.side_effect = lambda key, default=None: {
        "settings": {
            "profile": "local_lm_studio",
            "max_rounds": 3,
            "threshold": 0.75,
            "enable_fact_check": True,
            "enable_memory": True,
            "variant": "auto",
        },
        "prompt_manager": MagicMock(),
        "dms": MagicMock(),
        "selected_project_id": "proj1",
        "selected_document_id": "doc1",
        "session_db": MagicMock(),
        "rag_context": None,
    }.get(key, default)
    return session


class TestDebateEngineRAG:
    @pytest.mark.asyncio
    async def test_debate_with_rag_context(self, engine_with_rag, mock_llm_response):
        async def side_effect(*args, **kwargs):
            system_prompt = args[0] if len(args) > 0 else kwargs.get("system_prompt", "")
            user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            if "Moderator" in system_prompt or "Bewert" in system_prompt or "Bewerte" in user_prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return mock_llm_response()

        engine_with_rag.router.call = AsyncMock(side_effect=side_effect)
        state = await engine_with_rag.run("Test topic")

        assert "## RAG Context" in state.context
        assert "Test RAG Context" in state.context
        assert state.final_consensus >= 0.75

    @pytest.mark.asyncio
    async def test_debate_without_rag_context(self, engine_without_rag, mock_llm_response):
        async def side_effect(*args, **kwargs):
            system_prompt = args[0] if len(args) > 0 else kwargs.get("system_prompt", "")
            user_prompt = args[1] if len(args) > 1 else kwargs.get("user_prompt", "")
            if "Moderator" in system_prompt or "Bewert" in system_prompt or "Bewerte" in user_prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return mock_llm_response()

        engine_without_rag.router.call = AsyncMock(side_effect=side_effect)
        state = await engine_without_rag.run("Test topic")

        assert "## RAG Context" not in state.context
        assert state.final_consensus >= 0.75

    @pytest.mark.asyncio
    async def test_rag_context_injected_into_prompts(self, engine_with_rag, mock_llm_response):
        call_args_list = []

        async def side_effect(*args, **kwargs):
            call_args_list.append(args)
            prompt = args[0] if args else kwargs.get("system_prompt", "")
            if "Moderator" in prompt or "Bewert" in prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return mock_llm_response()

        engine_with_rag.router.call = AsyncMock(side_effect=side_effect)
        await engine_with_rag.run("Test topic")

        strategist_call = call_args_list[0]
        strategist_user_prompt = strategist_call[1] if len(strategist_call) > 1 else ""
        assert "## RAG Context" in strategist_user_prompt
        assert "Test RAG Context" in strategist_user_prompt

    @pytest.mark.asyncio
    async def test_rag_context_preview_in_output(self, engine_with_rag, mock_llm_response):
        async def side_effect(*args, **kwargs):
            prompt = args[0] if args else kwargs.get("system_prompt", "")
            if "Moderator" in prompt or "Bewert" in prompt:
                return {"content": "0.80", "tokens_used": 50, "model": "test", "finish_reason": "stop"}
            return mock_llm_response()

        engine_with_rag.router.call = AsyncMock(side_effect=side_effect)
        state = await engine_with_rag.run("Test topic")

        assert "## RAG Context" in state.context
        assert len(state.rounds) >= 1
        assert "Test RAG Context" not in state.rounds[0]["draft_preview"]


class TestChainlitRAG:
    @pytest.mark.asyncio
    async def test_chainlit_passes_rag_context_to_engine(
        self, mock_dms, mock_chainlit_message, mock_chainlit_session
    ):
        mock_chainlit_session.get.side_effect = lambda key, default=None: {
            "settings": {
                "profile": "local_lm_studio",
                "max_rounds": 3,
                "threshold": 0.75,
                "enable_fact_check": True,
                "enable_memory": True,
                "variant": "auto",
            },
            "prompt_manager": MagicMock(),
            "dms": mock_dms,
            "selected_project_id": "proj1",
            "selected_document_id": "doc1",
            "session_db": MagicMock(),
            "rag_context": "Session RAG Context"
        }.get(key, default)

        with patch("src.ui.chainlit_app.DebateEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.run = AsyncMock()
            state = MagicMock()
            state.used_variant = "auto"
            state.final_consensus = 0.8
            state.output = "Test output"
            state.session_id = "test123"
            mock_engine.run.return_value = state
            mock_engine.logger = MagicMock()
            mock_engine.logger.get_session_log.return_value = []
            mock_engine.privacy = MagicMock()
            mock_engine_cls.return_value = mock_engine

            with patch("src.ui.chainlit_app.cl.user_session", mock_chainlit_session), \
                 patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
                 patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed", "metadata": {}}), \
                 patch("src.ui.chainlit_app.ReportGenerator") as mock_gen, \
                 patch("src.ui.chainlit_app.cl.Step"), \
                 patch("src.ui.chainlit_app.SessionDB"), \
                 patch("src.ui.chainlit_app.cl.Text"), \
                 patch("src.ui.chainlit_app.cl.File"), \
                 patch("chainlit.context.context_var") as mock_ctx_var:
                mock_ctx = MagicMock()
                mock_ctx.session = MagicMock()
                mock_ctx.session.thread_id = "test"
                mock_ctx_var.get.return_value = mock_ctx

                mock_msg.return_value.send = AsyncMock()
                mock_gen.return_value.generate = AsyncMock(return_value=MagicMock(name="report.docx"))

                await chainlit_app.main(mock_chainlit_message)

        call_args = mock_engine.run.call_args
        context_arg = call_args[0][0]
        assert "## RAG Context" in context_arg
        assert "Session RAG Context" in context_arg

    @pytest.mark.asyncio
    async def test_chainlit_retrieves_rag_based_on_topic(
        self, mock_dms, mock_chainlit_message, mock_chainlit_session
    ):
        mock_chainlit_session.get.side_effect = lambda key, default=None: {
            "settings": {
                "profile": "local_lm_studio",
                "max_rounds": 3,
                "threshold": 0.75,
                "enable_fact_check": True,
                "enable_memory": True,
                "variant": "auto",
            },
            "prompt_manager": MagicMock(),
            "dms": mock_dms,
            "selected_project_id": "proj1",
            "selected_document_id": "doc1",
            "session_db": MagicMock(),
            "rag_context": None
        }.get(key, default)

        with patch("src.ui.chainlit_app.DebateEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.run = AsyncMock()
            state = MagicMock()
            state.used_variant = "auto"
            state.final_consensus = 0.8
            state.output = "Test output"
            state.session_id = "test123"
            mock_engine.run.return_value = state
            mock_engine.logger = MagicMock()
            mock_engine.logger.get_session_log.return_value = []
            mock_engine.privacy = MagicMock()
            mock_engine_cls.return_value = mock_engine

            mock_dms.auto_retrieve_for_topic.return_value = [
                {"text": "RAG chunk 1", "source": "test.pdf", "chunk_index": 0, "project_id": "proj1"}
            ]

            with patch("src.ui.chainlit_app.cl.user_session", mock_chainlit_session), \
                 patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
                 patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed", "metadata": {}}), \
                 patch("src.ui.chainlit_app.ReportGenerator") as mock_gen, \
                 patch("src.ui.chainlit_app.cl.Step"), \
                 patch("src.ui.chainlit_app.SessionDB"), \
                 patch("src.ui.chainlit_app.cl.Text"), \
                 patch("src.ui.chainlit_app.cl.File"), \
                 patch("chainlit.context.context_var") as mock_ctx_var:
                mock_ctx = MagicMock()
                mock_ctx.session = MagicMock()
                mock_ctx.session.thread_id = "test"
                mock_ctx_var.get.return_value = mock_ctx

                mock_msg.return_value.send = AsyncMock()
                mock_gen.return_value.generate = AsyncMock(return_value=MagicMock(name="report.docx"))

                topic = mock_chainlit_message.content
                rag_context_chunks = mock_dms.auto_retrieve_for_topic(topic, project_id="proj1")
                formatted_rag = RAGContextFormatter().format(rag_context_chunks)
                mock_chainlit_session.get.side_effect = lambda key, default=None: {
                    **mock_chainlit_session.get.side_effect(key, default),
                    "rag_context": formatted_rag
                }.get(key, default) if key == "rag_context" else mock_chainlit_session.get.side_effect(key, default)

                await chainlit_app.main(mock_chainlit_message)

        mock_dms.auto_retrieve_for_topic.assert_called_once_with(
            mock_chainlit_message.content, project_id="proj1", k=5
        )

    @pytest.mark.asyncio
    async def test_chainlit_shows_rag_context_preview(
        self, mock_dms, mock_chainlit_message, mock_chainlit_session
    ):
        messages_sent = []

        async def mock_send(self):
            nonlocal messages_sent
            messages_sent.append(self.content)
            return MagicMock()

        with patch("src.ui.chainlit_app.DebateEngine") as mock_engine_cls:
            mock_engine = MagicMock()
            mock_engine.run = AsyncMock()
            state = MagicMock()
            state.used_variant = "auto"
            state.final_consensus = 0.8
            state.output = "Test output"
            state.session_id = "test123"
            mock_engine.run.return_value = state
            mock_engine.logger = MagicMock()
            mock_engine.logger.get_session_log.return_value = []
            mock_engine.privacy = MagicMock()
            mock_engine_cls.return_value = mock_engine

            mock_chainlit_session.get.side_effect = lambda key, default=None: {
                "settings": {
                    "profile": "local_lm_studio",
                    "max_rounds": 3,
                    "threshold": 0.75,
                    "enable_fact_check": True,
                    "enable_memory": True,
                    "variant": "auto",
                },
                "prompt_manager": MagicMock(),
                "dms": mock_dms,
                "selected_project_id": "proj1",
                "selected_document_id": "doc1",
                "session_db": MagicMock(),
                "rag_context": "Test RAG Context Preview"
            }.get(key, default)

            with patch("src.ui.chainlit_app.cl.user_session", mock_chainlit_session), \
                 patch("src.ui.chainlit_app.cl.Message") as mock_msg_cls, \
                 patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed", "metadata": {}}), \
                 patch("src.ui.chainlit_app.ReportGenerator") as mock_gen, \
                 patch("src.ui.chainlit_app.cl.Step"), \
                 patch("src.ui.chainlit_app.SessionDB"), \
                 patch("src.ui.chainlit_app.cl.Text"), \
                 patch("src.ui.chainlit_app.cl.File"), \
                 patch("chainlit.context.context_var") as mock_ctx_var:
                mock_ctx = MagicMock()
                mock_ctx.session = MagicMock()
                mock_ctx.session.thread_id = "test"
                mock_ctx_var.get.return_value = mock_ctx

                mock_msg_instance = MagicMock()
                mock_msg_instance.send = mock_send
                mock_msg_cls.return_value = mock_msg_instance
                mock_gen.return_value.generate = AsyncMock(return_value=MagicMock(name="report.docx"))

                await chainlit_app.main(mock_chainlit_message)

        assert any("RAG Context" in msg for msg in messages_sent), "RAG context preview not shown"


class TestRAGContextFormatter:
    def test_formatter_empty_chunks(self, rag_formatter):
        assert rag_formatter.format([]) == ""

    def test_formatter_single_chunk(self, rag_formatter):
        chunks = [{"text": "Test chunk", "metadata": {"file_name": "test.pdf", "chunk_index": 0}}]
        result = rag_formatter.format(chunks)
        assert "[Document 1 from test.pdf]: Test chunk" in result

    def test_formatter_multiple_chunks(self, rag_formatter):
        chunks = [
            {"text": "Chunk 1", "metadata": {"file_name": "f1.pdf", "chunk_index": 0}},
            {"text": "Chunk 2", "metadata": {"file_name": "f2.pdf", "chunk_index": 1}}
        ]
        result = rag_formatter.format(chunks)
        assert "[Document 1 from f1.pdf]: Chunk 1" in result
        assert "[Document 2 from f2.pdf]: Chunk 2" in result

    def test_formatter_truncation(self, rag_formatter):
        chunks = [{"text": "A" * 5000, "metadata": {"file_name": "test.pdf", "chunk_index": 0}}]
        result = rag_formatter.format(chunks, max_chars=100)
        assert len(result) <= 100
        assert result.endswith("...")
