"""Tests for web search service and related helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.services.web_search import (
    WebSearchResult,
    WebSearchTool,
    extract_search_markers,
    extract_search_queries,
    format_search_results,
)
from backend.workflow.legacy_nodes import _append_search_instruction

# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------


class TestWebSearchToolInit:
    def test_default_params(self):
        tool = WebSearchTool()
        assert tool.url == "http://localhost:8080"
        assert tool.max_results == 5
        assert tool.region == "de-de"
        assert tool.timeout == 8.0
        assert tool._client is None

    def test_custom_params(self):
        tool = WebSearchTool(url="http://searxng:9090", max_results=10, region="en-us", timeout=5.0)
        assert tool.url == "http://searxng:9090"
        assert tool.max_results == 10
        assert tool.region == "en-us"
        assert tool.timeout == 5.0

    def test_url_trailing_slash_stripped(self):
        tool = WebSearchTool(url="http://localhost:8080/")
        assert tool.url == "http://localhost:8080"


class TestWebSearchToolSearXNG:
    @pytest.mark.asyncio
    async def test_searxng_returns_results(self):
        """SearXNG returns structured results from JSON API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com/test",
                    "content": "A test snippet",
                    "engine": "google",
                    "publishedDate": "2024-01-01",
                },
                {
                    "title": "Second Result",
                    "url": "https://example.com/second",
                    "content": "Another snippet",
                    "engine": "bing",
                    "publishedDate": "",
                },
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        tool = WebSearchTool()
        tool._client = mock_client

        results = await tool._search_searxng("test query")

        assert len(results) == 2
        assert results[0]["title"] == "Test Result"
        assert results[0]["url"] == "https://example.com/test"
        assert results[0]["snippet"] == "A test snippet"
        assert results[0]["engine"] == "google"
        assert results[1]["engine"] == "bing"

    @pytest.mark.asyncio
    async def test_searxng_respects_max_results(self):
        """Results are capped at max_results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "title": f"Result {i}",
                    "url": f"https://example.com/{i}",
                    "content": f"Snippet {i}",
                    "engine": "google",
                }
                for i in range(10)
            ]
        }
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        tool = WebSearchTool(max_results=3)
        tool._client = mock_client

        results = await tool._search_searxng("test query")
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_searxng_returns_empty_on_error(self):
        """SearXNG returns empty list on HTTP error."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))

        tool = WebSearchTool()
        tool._client = mock_client

        results = await tool._search_searxng("test query")
        assert results == []

    @pytest.mark.asyncio
    async def test_searxng_returns_empty_on_parse_error(self):
        """SearXNG returns empty list on JSON parse error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = ValueError("Invalid JSON")
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        tool = WebSearchTool()
        tool._client = mock_client

        results = await tool._search_searxng("test query")
        assert results == []


class TestWebSearchToolSearch:
    @pytest.mark.asyncio
    async def test_search_falls_back_to_ddg(self):
        """When SearXNG returns empty, search tries DuckDuckGo."""
        tool = WebSearchTool()
        tool._search_searxng = AsyncMock(return_value=[])
        tool._search_ddg = AsyncMock(
            return_value=[
                {
                    "title": "DDG Result",
                    "url": "https://ddg.com",
                    "snippet": "DDG snippet",
                    "engine": "duckduckgo",
                    "date": "",
                }
            ]
        )

        results = await tool.search("test query")
        assert len(results) == 1
        assert results[0]["engine"] == "duckduckgo"
        tool._search_ddg.assert_called_once_with("test query")

    @pytest.mark.asyncio
    async def test_search_skips_ddg_when_searxng_succeeds(self):
        """When SearXNG returns results, DuckDuckGo is not called."""
        tool = WebSearchTool()
        tool._search_searxng = AsyncMock(
            return_value=[
                {
                    "title": "SearXNG Result",
                    "url": "https://searxng.com",
                    "snippet": "OK",
                    "engine": "google",
                    "date": "",
                }
            ]
        )
        tool._search_ddg = AsyncMock()

        results = await tool.search("test query")
        assert len(results) == 1
        tool._search_ddg.assert_not_called()


class TestWebSearchToolClose:
    @pytest.mark.asyncio
    async def test_close_closes_client(self):
        """close() acloses the HTTP client and sets it to None."""
        mock_client = AsyncMock()
        tool = WebSearchTool()
        tool._client = mock_client

        await tool.close()
        mock_client.aclose.assert_called_once()
        assert tool._client is None

    @pytest.mark.asyncio
    async def test_close_noop_when_no_client(self):
        """close() is a no-op when no client exists."""
        tool = WebSearchTool()
        await tool.close()  # Should not raise


class TestWebSearchToolIsAvailable:
    @pytest.mark.asyncio
    async def test_is_available_true_on_healthz(self):
        """is_available returns True when /healthz returns 200."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        tool = WebSearchTool()
        tool._client = mock_client

        assert await tool.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_error(self):
        """is_available returns False when connection fails."""
        import httpx

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=httpx.RequestError("Connection refused"))

        tool = WebSearchTool()
        tool._client = mock_client

        assert await tool.is_available() is False


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


class TestExtractSearchQueries:
    def test_basic_extraction(self):
        """Extracts first sentence as primary query."""
        queries = extract_search_queries(
            "Die Bundesregierung plant neue Maßnahmen. Dies betrifft viele Bürger.",
            "strategist",
        )
        assert len(queries) >= 1
        assert "Die Bundesregierung plant neue Maßnahmen" in queries[0]

    def test_moderator_extracts_claims(self):
        """Moderator role extracts sentences with claim keywords."""
        queries = extract_search_queries(
            "Laut einer Studie der Universität München steigen die Temperaturen. Die Regierung plant neue Maßnahmen.",
            "moderator",
        )
        assert len(queries) >= 2
        assert any("Studie" in q for q in queries)

    def test_respects_max_queries(self):
        """Returns at most max_queries results."""
        queries = extract_search_queries(
            "Laut einer Studie steigen die Temperaturen. "
            "According to research, data shows trends. "
            "A report by the WHO confirms this. "
            "Additional sentence without keywords.",
            "moderator",
            max_queries=2,
        )
        assert len(queries) <= 2

    def test_empty_input(self):
        """Returns empty list for empty input."""
        queries = extract_search_queries("", "strategist")
        assert queries == []

    def test_long_text_truncated(self):
        """First sentence is truncated to 200 chars."""
        long_text = "A" * 300 + ". Next sentence."
        queries = extract_search_queries(long_text, "strategist")
        assert len(queries) >= 1
        assert len(queries[0]) <= 200


class TestExtractSearchMarkers:
    def test_single_marker(self):
        content = "I think we need to verify this. [SEARCH: current GDP Germany 2024]"
        markers = extract_search_markers(content)
        assert markers == ["current GDP Germany 2024"]

    def test_multiple_markers(self):
        content = "First claim [SEARCH: inflation rate EU 2024] and second claim [SEARCH: unemployment statistics Germany]"
        markers = extract_search_markers(content)
        assert len(markers) == 2
        assert markers[0] == "inflation rate EU 2024"
        assert markers[1] == "unemployment statistics Germany"

    def test_no_markers(self):
        content = "This is a normal response without any search requests."
        markers = extract_search_markers(content)
        assert markers == []

    def test_marker_with_extra_spaces(self):
        content = "[SEARCH:   query with spaces   ]"
        markers = extract_search_markers(content)
        assert markers == ["query with spaces   "]

    def test_nested_brackets(self):
        content = "[SEARCH: query [with] brackets]"
        markers = extract_search_markers(content)
        # Non-greedy match stops at first ]
        assert markers == ["query [with"]


class TestFormatSearchResults:
    def test_format_with_results_de(self):
        results: list[WebSearchResult] = [
            {
                "title": "Ergebnis 1",
                "url": "https://example.com/1",
                "snippet": "Snippet 1",
                "engine": "google",
                "date": "",
            },
            {
                "title": "Ergebnis 2",
                "url": "https://example.com/2",
                "snippet": "Snippet 2",
                "engine": "bing",
                "date": "",
            },
        ]
        formatted = format_search_results(results, language="de")
        assert "## Web-Recherche" in formatted
        assert "Ergebnis 1" in formatted
        assert "https://example.com/1" in formatted
        assert "Quelle" in formatted

    def test_format_with_results_en(self):
        results: list[WebSearchResult] = [
            {
                "title": "Result 1",
                "url": "https://example.com/1",
                "snippet": "Snippet 1",
                "engine": "google",
                "date": "",
            },
        ]
        formatted = format_search_results(results, language="en")
        assert "## Web Research" in formatted
        assert "Result 1" in formatted
        assert "Source" in formatted

    def test_format_empty_results_de(self):
        formatted = format_search_results([], language="de")
        assert "Keine Ergebnisse" in formatted

    def test_format_empty_results_en(self):
        formatted = format_search_results([], language="en")
        assert "No results found" in formatted


# ---------------------------------------------------------------------------
# Search instruction injection
# ---------------------------------------------------------------------------


class TestAppendSearchInstruction:
    def test_off_mode_returns_unchanged(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "off", "de")
        assert result == prompt

    def test_unknown_mode_returns_unchanged(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "unknown", "de")
        assert result == prompt

    def test_required_mode_de(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "required", "de")
        assert "Web-Recherche" in result
        assert result.startswith(prompt)
        assert len(result) > len(prompt)

    def test_required_mode_en(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "required", "en")
        assert "Web Research" in result
        assert "MUST incorporate" in result

    def test_optional_mode_de(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "optional", "de")
        assert "Web-Suche" in result
        assert "[SEARCH:" in result

    def test_optional_mode_en(self):
        prompt = "You are a debate agent."
        result = _append_search_instruction(prompt, "optional", "en")
        assert "Web Search Capability" in result
        assert "[SEARCH:" in result


# ---------------------------------------------------------------------------
# SearchMode schema validation
# ---------------------------------------------------------------------------


class TestSearchModeSchema:
    def test_search_mode_enum_values(self):
        from backend.models.schemas import SearchMode

        assert SearchMode.OFF == "off"
        assert SearchMode.OPTIONAL == "optional"
        assert SearchMode.REQUIRED == "required"

    def test_debate_request_default_search_mode(self):
        from backend.models.schemas import DebateRequest, SearchMode

        req = DebateRequest(case={"text": "Test case"})
        assert req.search_mode == SearchMode.OFF

    def test_debate_request_with_search_mode(self):
        from backend.models.schemas import DebateRequest, SearchMode

        req = DebateRequest(case={"text": "Test case"}, search_mode=SearchMode.REQUIRED)
        assert req.search_mode == SearchMode.REQUIRED

    def test_debate_request_invalid_search_mode(self):
        from pydantic import ValidationError

        from backend.models.schemas import DebateRequest

        with pytest.raises(ValidationError):
            DebateRequest(case={"text": "Test case"}, search_mode="invalid")
