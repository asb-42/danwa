import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.ui.dms_dashboard import show_projects, create_project_flow, handle_file_upload


@pytest.fixture
def mock_dms():
    dms = Mock()
    dms.list_projects.return_value = [
        {"id": "p1", "name": "Test Project", "description": "Test"},
        {"id": "p2", "name": "Another Project", "description": ""},
    ]
    dms.create_project.return_value = "p3"
    dms.delete_project.return_value = True
    dms.list_documents.return_value = [
        {"id": "d1", "filename": "test.pdf", "uploaded_at": "2026-04-28"},
    ]
    dms.upload_document.return_value = "d1"
    return dms


@pytest.fixture
def mock_session(mock_dms):
    with patch("src.ui.dms_dashboard.cl.user_session") as session:
        session.get.side_effect = lambda key: mock_dms if key == "dms" else ("p1" if key == "selected_project_id" else None)
        yield session


@pytest.mark.asyncio
async def test_show_projects_lists_items(mock_session, mock_dms):
    with patch("src.ui.dms_dashboard.cl.Message") as msg:
        msg.return_value.send = AsyncMock()
        await show_projects()
        mock_dms.list_projects.assert_called_once()
        assert "Test Project" in msg.call_args[1]["content"]


@pytest.mark.asyncio
async def test_create_project_success(mock_session, mock_dms):
    with patch("src.ui.dms_dashboard.cl.AskUserMessage") as ask:
        ask.return_value.send = AsyncMock(side_effect=[
            Mock(content="New Project"),
            Mock(content="New Desc"),
        ])
        with patch("src.ui.dms_dashboard.cl.Message") as msg:
            msg.return_value.send = AsyncMock()
            await create_project_flow()
            mock_dms.create_project.assert_called_once_with("New Project", "New Desc")


@pytest.mark.asyncio
async def test_upload_document_success(mock_session, mock_dms):
    mock_file = Mock()
    mock_file.name = "test.pdf"
    mock_file.path = "/tmp/test.pdf"
    with patch("src.ui.dms_dashboard.cl.Message") as msg_mock:
        msg_instance = Mock()
        msg_instance.send = AsyncMock()
        msg_instance.update = AsyncMock()
        msg_mock.return_value = msg_instance
        with patch("src.ui.dms_dashboard.show_documents") as _mock_show:
            with patch("src.ui.dms_dashboard.asyncio.sleep", new_callable=AsyncMock):
                await handle_file_upload([mock_file])
                mock_dms.upload_document.assert_called_once_with("p1", "/tmp/test.pdf")
                msg_instance.send.assert_awaited_once()
                assert msg_instance.update.await_count == 3


@pytest.mark.asyncio
async def test_upload_progress_shows_percentages(mock_session, mock_dms):
    mock_file = Mock()
    mock_file.name = "test.pdf"
    mock_file.path = "/tmp/test.pdf"
    with patch("src.ui.dms_dashboard.cl.Message") as msg_mock:
        msg_instance = Mock()
        msg_instance.send = AsyncMock()
        msg_instance.update = AsyncMock()
        msg_mock.return_value = msg_instance
        with patch("src.ui.dms_dashboard.show_documents") as _mock_show:
            with patch("src.ui.dms_dashboard.asyncio.sleep", new_callable=AsyncMock):
                await handle_file_upload([mock_file])
                assert msg_mock.call_args_list[0][1]["content"] == "📤 Uploading test.pdf... (0%)"
                assert msg_instance.update.await_count == 3
                assert "✅ Uploaded 'test.pdf'" in msg_instance.content
