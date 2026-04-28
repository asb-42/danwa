import httpx
import logging
import json
from typing import List, Dict
from urllib.parse import quote

logger = logging.getLogger(__name__)


def extract_json_list(text: str) -> list:
    """
    Extract a JSON list from text. Handles LLM responses that may include
    extra text around the JSON array.
    """
    import json
    import re
    match = re.search(r'\[.*?\]', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, TypeError):
        pass
    logger.warning(f"Could not extract JSON list from: {text[:100]}")
    return []


class WebSearchTool:
    def __init__(
        self,
        engine: str = "searxng",
        searx_url: str = "http://localhost:8080",
        max_results: int = 5,
        region: str = "de-de"
    ):
        self.engine = engine
        self.searx_url = searx_url.rstrip("/")
        self.max_results = max_results
        self.region = region
        self.client = httpx.AsyncClient(timeout=8.0, follow_redirects=True)

    async def search(self, query: str) -> List[Dict]:
        if self.engine == "searxng":
            return await self._search_searxng(query)
        # Fallback-Logik kann hier ergänzt werden
        logger.warning(f"Unknown search engine: {self.engine}")
        return []

    async def _search_searxng(self, query: str) -> List[Dict]:
        try:
            url = f"{self.searx_url}/search"
            params = {
                "q": query,
                "format": "json",
                "categories": "general",
                "language": self.region,
                "max_results": self.max_results,
                "safesearch": 1
            }
            resp = await self.client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for r in data.get("results", [])[:self.max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "engine": r.get("engine", ""),
                    "date": r.get("publishedDate", "")
                })
            return results
        except httpx.RequestError as e:
            logger.warning(f"SearXNG request failed for '{query}': {e}")
        except Exception as e:
            logger.warning(f"SearXNG parse failed for '{query}': {e}")
        return []

    async def close(self):
        await self.client.aclose()