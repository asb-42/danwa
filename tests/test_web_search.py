import pytest
from src.tools.web_search import WebSearchTool, extract_json_list
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


@pytest.fixture
def search_tool():
    return WebSearchTool(
        engine="searxng",
        searx_url="http://localhost:8080",
        max_results=3
    )


@pytest.mark.asyncio
async def test_search_init(search_tool):
    assert search_tool.engine == "searxng"
    assert search_tool.searx_url == "http://localhost:8080"
    assert search_tool.max_results == 3


@pytest.mark.asyncio
async def test_search_searxng(search_tool):
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "results": [
            {"title": "Result 1", "url": "http://example.com/1", "content": "Snippet 1", "engine": "google"},
            {"title": "Result 2", "url": "http://example.com/2", "content": "Snippet 2", "engine": "bing"}
        ]
    }
    mock_response.raise_for_status = MagicMock()
    
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    
    with patch("src.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        results = await search_tool.search("test query")
    
    assert len(results) == 2
    assert results[0]["title"] == "Result 1"
    assert "url" in results[0]
    assert "snippet" in results[0]


@pytest.mark.asyncio
async def test_search_searxng_empty_results(search_tool):
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()
    
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch("src.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        results = await search_tool.search("test")
    
    assert results == []


@pytest.mark.asyncio
async def test_search_searxng_request_fails(search_tool):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection failed"))
    
    with patch("src.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        results = await search_tool.search("test")
    
    assert results == []


@pytest.mark.asyncio
async def test_search_searxng_parse_error(search_tool):
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.side_effect = Exception("Parse error")
    
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    
    with patch("src.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        results = await search_tool.search("test")
    
    assert results == []


def test_extract_json_list_valid():
    text = '["Claim 1", "Claim 2", "Claim 3"]'
    result = extract_json_list(text)
    assert isinstance(result, list)
    assert len(result) == 3


def test_extract_json_list_with_extra_text():
    text = 'Here is the result: ["Claim 1", "Claim 2"] and that is it.'
    result = extract_json_list(text)
    assert isinstance(result, list)
    assert len(result) == 2


def test_extract_json_list_invalid():
    text = "No JSON here"
    result = extract_json_list(text)
    assert result == []


def test_extract_json_list_malformed_json():
    text = '["unclosed string]'
    result = extract_json_list(text)
    assert result == []


def test_extract_json_list_empty():
    text = ''
    result = extract_json_list(text)
    assert result == []


@pytest.mark.asyncio
async def test_search_with_region(search_tool):
    search_tool.region = "en-us"
    mock_response = MagicMock()
    mock_response.json.return_value = {"results": []}
    mock_response.raise_for_status = MagicMock()
    
    captured_params = {}
    mock_client = MagicMock()
    async def capture_get(url, params=None, **kwargs):
        captured_params.update(params)
        return mock_response
    mock_client.get = capture_get
    
    with patch("src.tools.web_search.httpx.AsyncClient", return_value=mock_client):
        await search_tool.search("test")
    
    assert captured_params.get("language") == "en-us"


@pytest.mark.asyncio
async def test_close(search_tool):
    search_tool.client = MagicMock()
    search_tool.client.aclose = AsyncMock()
    await search_tool.close()
    search_tool.client.aclose.assert_called_once()
