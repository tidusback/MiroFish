"""
Wikipedia Provider
==================
Full-text search via the MediaWiki API.
Provides encyclopedic baseline knowledge — useful for fact-checking
and finding subjects that SEO-driven search might bury.

No API key required.
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.wikipedia")


class WikipediaProvider(BaseProvider):
    NAME = "Wikipedia"
    ID = "wikipedia"
    SOURCE_TYPE = SourceType.ENCYCLOPEDIA
    REQUIRES_KEY = False

    _SEARCH_URL = "https://en.wikipedia.org/w/api.php"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            headers = {**self._DEFAULT_HEADERS}

            # Step 1 – full-text search for page titles + snippets
            params = {
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "sroffset": (page - 1) * max_results,
                "srprop": "snippet|titlesnippet|sectionsnippet|timestamp",
                "format": "json",
                "utf8": 1,
            }

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            import re

            for item in data.get("query", {}).get("search", []):
                title = item.get("title", "")
                snippet = re.sub(r"<[^>]+>", "", item.get("snippet", ""))
                page_url = f"https://en.wikipedia.org/wiki/{title.replace(' ', '_')}"

                results.append(
                    SearchResult(
                        title=title,
                        url=page_url,
                        snippet=snippet,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        published_at=item.get("timestamp"),
                        extra={
                            "wordcount": item.get("wordcount", 0),
                            "ns": item.get("ns", 0),
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"Wikipedia search failed: {exc}")

        return results
