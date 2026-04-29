import pytest
from unittest.mock import MagicMock, patch, AsyncMock
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
def mock_dms_dashboard():
    with patch("src.ui.chainlit_app.dms_dashboard") as mock:
        mock.start = AsyncMock()
        yield mock

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
        mock_dms_class.return_value = instance
        yield instance


def test_dms_import():
    assert hasattr(chainlit_app, "dms_dashboard")
    assert chainlit_app.dms_dashboard is not None


@pytest.mark.asyncio
async def test_start_actions_include_dms_button(mock_dms_dashboard):
    captured_widgets = []
    captured_actions = []
    
    original_select = chainlit_app.cl.input_widget.Select
    def mock_select_creator(**kwargs):
        captured_widgets.append(kwargs)
        return original_select(**kwargs)
    
    original_action = chainlit_app.cl.Action
    def mock_action_creator(**kwargs):
        captured_actions.append(kwargs)
        return original_action(**kwargs)
    
    with patch("src.ui.chainlit_app.DMS") as mock_dms_class:
        mock_dms_instance = MagicMock()
        mock_dms_instance.list_projects.return_value = [
            {"id": "proj1", "name": "Test Project", "description": ""}
        ]
        mock_dms_class.return_value = mock_dms_instance
        
        with patch("src.ui.chainlit_app.cl.input_widget.Select", side_effect=mock_select_creator), \
             patch("src.ui.chainlit_app.cl.Action", side_effect=mock_action_creator):
            mock_session = MagicMock()
            mock_session.get.return_value = {}
            with patch("src.ui.chainlit_app.cl.user_session", mock_session):
                with patch("src.ui.chainlit_app.cl.ChatSettings") as mock_settings:
                    mock_settings.return_value.send = AsyncMock()
                    with patch("src.ui.chainlit_app.cl.Message") as mock_msg:
                        mock_msg.return_value.send = AsyncMock()
                        with patch("chainlit.context.context_var") as mock_ctx_var:
                            mock_ctx = MagicMock()
                            mock_ctx.session = MagicMock()
                            mock_ctx.session.thread_id = "test"
                            mock_ctx_var.get.return_value = mock_ctx
                            await chainlit_app.start()
    
    widget_ids = [w.get("id") for w in captured_widgets]
    assert "selected_project_id" in widget_ids
    assert "selected_document_id" in widget_ids
    
    dms_actions = [a for a in captured_actions if a.get("name") == "open_dms"]
    assert len(dms_actions) == 1
    assert dms_actions[0]["label"] == "📁 DMS Dashboard"


@pytest.mark.asyncio
async def test_on_settings_update(mock_dms):
    settings = {
        "selected_project_id": "proj1",
        "selected_document_id": "doc1",
        "profile": "local_lm_studio",
        "max_rounds": 3,
        "threshold": 0.75,
        "enable_fact_check": True,
        "enable_memory": True,
        "variant": "auto",
    }
    
    mock_session = MagicMock()
    mock_session.get.return_value = mock_dms
    with patch("src.ui.chainlit_app.cl.user_session", mock_session), \
         patch("src.ui.chainlit_app.cl.Message") as mock_msg:
        mock_msg.return_value.send = AsyncMock()
        await chainlit_app.on_settings_update(settings)
    
    assert mock_session.set.call_args_list[0][0][0] == "selected_project_id"
    assert mock_session.set.call_args_list[0][0][1] == "proj1"
    mock_msg.return_value.send.assert_awaited_once()


@pytest.fixture
def mock_debate_engine():
    with patch("src.ui.chainlit_app.DebateEngine") as mock_engine_class:
        instance = MagicMock()
        instance.run = AsyncMock()
        state = MagicMock()
        state.used_variant = "auto"
        state.final_consensus = 0.8
        state.output = "Test output"
        state.session_id = "test123"
        instance.run.return_value = state
        instance.logger = MagicMock()
        instance.logger.get_session_log.return_value = []
        instance.privacy = MagicMock()
        mock_engine_class.return_value = instance
        yield instance


@pytest.fixture
def mock_message():
    msg = MagicMock()
    msg.content = "Test debate topic"
    msg.elements = []
    return msg


@pytest.mark.asyncio
async def test_rag_context_from_session_included_in_context(mock_debate_engine, mock_message, mock_dms):
    rag_context = "Test RAG context chunk 1\nTest RAG context chunk 2"
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda key, default=None: {
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
        "session_db": MagicMock(),
        "rag_context": rag_context,
    }.get(key, default)
    
    with patch("src.ui.chainlit_app.cl.user_session", mock_session), \
         patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
         patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed doc", "metadata": {}}) as mock_parse, \
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
        
        mock_message.elements = [MagicMock(name="test.pdf", path="/tmp/test.pdf")]
        
        await chainlit_app.main(mock_message)
    
    call_args = mock_debate_engine.run.call_args
    context_arg = call_args[0][0]
    assert "## RAG Context" in context_arg
    assert "Test RAG context chunk 1" in context_arg
    assert "## Parsed Documents" in context_arg


@pytest.mark.asyncio
async def test_context_assembly_with_parsed_docs_no_rag(mock_debate_engine, mock_message):
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda key, default=None: {
        "settings": {
            "profile": "local_lm_studio",
            "max_rounds": 3,
            "threshold": 0.75,
            "enable_fact_check": True,
            "enable_memory": True,
            "variant": "auto",
        },
        "prompt_manager": MagicMock(),
        "dms": None,
        "selected_project_id": None,
        "session_db": MagicMock(),
        "rag_context": None,
    }.get(key, default)
    
    with patch("src.ui.chainlit_app.cl.user_session", mock_session), \
         patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
         patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed doc text", "metadata": {"author": "test"}}) as mock_parse, \
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
        
        mock_message.elements = [MagicMock(name="test.pdf", path="/tmp/test.pdf")]
        
        await chainlit_app.main(mock_message)
    
    call_args = mock_debate_engine.run.call_args
    context_arg = call_args[0][0]
    assert "[Analysierte Dokumente]" in context_arg
    assert "parsed doc text" in context_arg
    assert "## RAG Context" not in context_arg


@pytest.mark.asyncio
async def test_no_rag_context_when_not_in_session(mock_debate_engine, mock_message):
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda key, default=None: {
        "settings": {
            "profile": "local_lm_studio",
            "max_rounds": 3,
            "threshold": 0.75,
            "enable_fact_check": True,
            "enable_memory": True,
            "variant": "auto",
        },
        "prompt_manager": MagicMock(),
        "dms": None,
        "selected_project_id": None,
        "session_db": MagicMock(),
        "rag_context": None,
    }.get(key, default)
    
    with patch("src.ui.chainlit_app.cl.user_session", mock_session), \
         patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
         patch("src.ui.chainlit_app.parser.parse_file", new_callable=AsyncMock, return_value={"text": "parsed", "metadata": {}}) as mock_parse, \
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
        
        mock_message.elements = [MagicMock(name="test.pdf", path="/tmp/test.pdf")]
        
        await chainlit_app.main(mock_message)
    
    call_args = mock_debate_engine.run.call_args
    context_arg = call_args[0][0]
    assert "## RAG Context" not in context_arg
    assert "[Analysierte Dokumente]" in context_arg


@pytest.mark.asyncio
async def test_rag_context_only_no_parsed_docs(mock_debate_engine, mock_message):
    rag_context = "Test RAG context from session"
    mock_session = MagicMock()
    mock_session.get.side_effect = lambda key, default=None: {
        "settings": {
            "profile": "local_lm_studio",
            "max_rounds": 3,
            "threshold": 0.75,
            "enable_fact_check": True,
            "enable_memory": True,
            "variant": "auto",
        },
        "prompt_manager": MagicMock(),
        "dms": None,
        "selected_project_id": None,
        "session_db": MagicMock(),
        "rag_context": rag_context,
    }.get(key, default)
    
    with patch("src.ui.chainlit_app.cl.user_session", mock_session), \
         patch("src.ui.chainlit_app.cl.Message") as mock_msg, \
         patch("src.ui.chainlit_app.DocumentParser") as mock_parser, \
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
        mock_parser.return_value.parse_file = AsyncMock(return_value={"text": "parsed", "metadata": {}})
        mock_gen.return_value.generate = AsyncMock(return_value=MagicMock(name="report.docx"))
        
        mock_message.elements = []
        
        await chainlit_app.main(mock_message)
    
    call_args = mock_debate_engine.run.call_args
    context_arg = call_args[0][0]
    assert "## RAG Context" in context_arg
    assert rag_context in context_arg
    assert "## Parsed Documents" not in context_arg
