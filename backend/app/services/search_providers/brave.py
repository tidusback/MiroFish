"""
Brave Search Provider
=====================
Uses Brave's independent search index (not a reseller of Google/Bing).
Privacy-first, no tracking, independent ranking algorithm.

API key: https://api.search.brave.com/  (free tier: 2,000 queries/month)
Set BRAVE_SEARCH_API_KEY in .env
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.brave")


class BraveSearchProvider(BaseProvider):
    NAME = "Brave Search"
    ID = "brave"
    SOURCE_TYPE = SourceType.WEB
    REQUIRES_KEY = True

    _API_URL = "https://api.search.brave.com/res/v1/web/search"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def is_available(self) -> bool:
        return bool(self._api_key)

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        if not self._api_key:
            return []

        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            offset = (page - 1) * max_results
            headers = {
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": self._api_key,
            }
            params = {
                "q": query,
                "count": min(max_results, 20),
                "offset": offset,
                "search_lang": "en",
                "safesearch": "off",  # No censorship
                "freshness": None,
                "text_decorations": False,
                "spellcheck": False,
            }
            # Remove None values
            params = {k: v for k, v in params.items() if v is not None}

            resp = requests.get(
                self._API_URL, headers=headers, params=params, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("web", {}).get("results", []):
                results.append(
                    SearchResult(
                        title=item.get("title", ""),
                        url=item.get("url", ""),
                        snippet=item.get("description", ""),
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        published_at=item.get("age"),
                        extra={
                            "language": item.get("language", ""),
                            "family_friendly": item.get("family_friendly", True),
                        },
                    )
                )
                if len(results) >= max_results:
                    break

        except Exception as exc:
            logger.warning(f"Brave Search failed: {exc}")

        return results
