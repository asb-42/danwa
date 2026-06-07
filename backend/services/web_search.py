"""Web search service — SearXNG-based search for debate agents.

Ported from the archived ``src/tools/web_search.py`` with typed results,
health check, and DuckDuckGo fallback.
"""

from __future__ import annotations

import logging
import re
from typing import TypedDict

import httpx

logger = logging.getLogger(__name__)


class WebSearchResult(TypedDict):
    """A single search result."""

    title: str
    url: str
    snippet: str
    engine: str
    date: str


class WebSearchTool:
    """Async web search via SearXNG (primary) or DuckDuckGo (fallback).

    Parameters
    ----------
    url:
        SearXNG base URL (e.g. ``http://localhost:8080``).
    max_results:
        Maximum number of results per query.
    region:
        Search region / language code (e.g. ``de-de``, ``en-us``).
    timeout:
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        url: str = "http://localhost:8080",
        max_results: int = 5,
        region: str = "de-de",
        timeout: float = 8.0,
    ) -> None:
        """Initialise WebSearchTool."""
        self.url = url.rstrip("/")
        self.max_results = max_results
        self.region = region
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def search(self, query: str) -> list[WebSearchResult]:
        """Execute a search query and return structured results.

        Tries SearXNG first; falls back to DuckDuckGo if SearXNG is
        unavailable.
        """
        results = await self._search_searxng(query)
        if not results:
            logger.info("SearXNG returned no results for '%s', trying DuckDuckGo", query)
            results = await self._search_ddg(query)
        return results

    async def is_available(self) -> bool:
        """Check whether SearXNG is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.url}/healthz", timeout=3.0)
            return resp.status_code == 200
        except Exception:
            # SearXNG may not expose /healthz — try a search instead
            try:
                client = await self._get_client()
                resp = await client.get(
                    f"{self.url}/search",
                    params={"q": "test", "format": "json", "pageno": 1},
                    timeout=5.0,
                )
                return resp.status_code == 200
            except Exception:
                return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # ------------------------------------------------------------------
    # Internal: SearXNG
    # ------------------------------------------------------------------

    async def _search_searxng(self, query: str) -> list[WebSearchResult]:
        """Search via SearXNG JSON API."""
        try:
            client = await self._get_client()
            params = {
                "q": query,
                "format": "json",
                "categories": "general",
                "language": self.region,
                "safesearch": 1,
                "pageno": 1,
            }
            resp = await client.get(f"{self.url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

            results: list[WebSearchResult] = []
            for r in data.get("results", [])[: self.max_results]:
                results.append(
                    {
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("content", ""),
                        "engine": r.get("engine", ""),
                        "date": r.get("publishedDate", ""),
                    }
                )
            return results
        except httpx.RequestError as exc:
            logger.warning("SearXNG request failed for '%s': %s", query, exc)
        except Exception as exc:
            logger.warning("SearXNG parse error for '%s': %s", query, exc)
        return []

    # ------------------------------------------------------------------
    # Internal: DuckDuckGo fallback
    # ------------------------------------------------------------------

    async def _search_ddg(self, query: str) -> list[WebSearchResult]:
        """Search via DuckDuckGo (requires ``duckduckgo-search`` package).

        Note: duckduckgo-search >= 8.x renamed to ``ddgs`` and removed
        AsyncDDGS. We use the sync DDGS wrapped in asyncio.to_thread().
        """
        try:
            import asyncio

            try:
                from ddgs import DDGS
            except ImportError:
                from duckduckgo_search import DDGS

            def _do_search() -> list[WebSearchResult]:
                """Do search the instance."""
                results: list[WebSearchResult] = []
                with DDGS() as ddgs:
                    for r in ddgs.text(
                        query,
                        region=self.region,
                        max_results=self.max_results,
                        timelimit="y",
                    ):
                        results.append(
                            {
                                "title": r.get("title", ""),
                                "url": r.get("href", ""),
                                "snippet": r.get("body", ""),
                                "engine": "duckduckgo",
                                "date": r.get("date", ""),
                            }
                        )
                return results

            return await asyncio.to_thread(_do_search)
        except ImportError:
            logger.debug("duckduckgo-search package not installed, skipping DDG fallback")
        except Exception as exc:
            logger.warning("DuckDuckGo search failed for '%s': %s", query, exc)
        return []

    # ------------------------------------------------------------------
    # Internal: HTTP client
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
            )
        return self._client


# ------------------------------------------------------------------
# Helper functions (used by workflow nodes)
# ------------------------------------------------------------------


def extract_search_queries(case_text: str, role: str, max_queries: int = 3) -> list[str]:
    """Extract search queries from the case text based on agent role.

    Uses simple heuristics (first sentence, proper nouns) — no LLM call.
    Returns 1–``max_queries`` queries.
    """
    queries: list[str] = []

    # Primary query: first sentence or first 200 chars of the case
    first_sentence = re.split(r"[.!?]\s", case_text, maxsplit=1)[0].strip()
    if len(first_sentence) > 200:
        first_sentence = first_sentence[:200]
    if first_sentence:
        queries.append(first_sentence)

    # For moderator: extract potential claims (sentences with keywords)
    if role == "moderator":
        claim_keywords = [
            "laut",
            "according",
            "behaupt",
            "claim",
            "statist",
            "studie",
            "study",
            "data",
            "daten",
            "evidence",
            "beweis",
            "report",
            "bericht",
            "research",
            "forschung",
        ]
        sentences = re.split(r"[.!?]\s", case_text)
        for sent in sentences:
            sent = sent.strip()
            if any(kw in sent.lower() for kw in claim_keywords):
                if len(sent) > 20 and len(sent) < 200:
                    queries.append(sent)
                    if len(queries) >= max_queries:
                        break

    return queries[:max_queries]


def extract_search_markers(content: str) -> list[str]:
    """Extract ``[SEARCH: query]`` markers from agent output."""
    return re.findall(r"\[SEARCH:\s*(.+?)\]", content)


def format_search_results(results: list[WebSearchResult], language: str = "de") -> str:
    """Format search results for injection into a prompt."""
    if not results:
        if language == "en":
            return "\n\n## Web Research\nNo results found.\n"
        return "\n\n## Web-Recherche\nKeine Ergebnisse gefunden.\n"

    header = "## Web Research" if language == "en" else "## Web-Recherche"
    source_label = "Source" if language == "en" else "Quelle"
    lines = [f"\n\n{header}\n"]

    for i, r in enumerate(results, 1):
        title = r["title"]
        url = r["url"]
        snippet = r["snippet"]
        lines.append(f"{i}. **{title}**")
        if snippet:
            lines.append(f"   {snippet}")
        lines.append(f"   {source_label}: {url}")
        lines.append("")

    return "\n".join(lines)
