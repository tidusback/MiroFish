"""
Hacker News Provider
====================
Searches HN via Algolia's free, public API.
Great for finding technical discussions, buried stories, and leaked info
that mainstream media ignores.

No API key required.
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.hackernews")


class HackerNewsProvider(BaseProvider):
    NAME = "Hacker News"
    ID = "hackernews"
    SOURCE_TYPE = SourceType.SOCIAL
    REQUIRES_KEY = False

    _API_URL = "https://hn.algolia.com/api/v1/search"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            params = {
                "query": query,
                "hitsPerPage": max_results,
                "page": page - 1,
                # stories + comments (uncensored community discussion)
                "tags": "(story,comment)",
            }

            resp = requests.get(
                self._API_URL, params=params, timeout=10
            )
            resp.raise_for_status()
            data = resp.json()

            for hit in data.get("hits", []):
                # Choose story URL or HN item URL
                story_url = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                title = hit.get("title") or hit.get("comment_text", "")[:120] or "HN Comment"
                snippet = _build_snippet(hit)

                results.append(
                    SearchResult(
                        title=title,
                        url=story_url,
                        snippet=snippet,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=hit.get("author"),
                        published_at=hit.get("created_at"),
                        extra={
                            "points": hit.get("points", 0),
                            "num_comments": hit.get("num_comments", 0),
                            "hn_url": f"https://news.ycombinator.com/item?id={hit.get('objectID')}",
                            "type": hit.get("_tags", [""])[0] if hit.get("_tags") else "",
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"HackerNews search failed: {exc}")

        return results


def _build_snippet(hit: dict) -> str:
    """Build a readable snippet from HN hit data."""
    parts = []
    if hit.get("comment_text"):
        text = hit["comment_text"]
        # Strip HTML tags
        import re
        text = re.sub(r"<[^>]+>", " ", text)
        parts.append(text[:300])
    if hit.get("points"):
        parts.append(f"↑{hit['points']} pts")
    if hit.get("num_comments"):
        parts.append(f"{hit['num_comments']} comments")
    return " · ".join(parts)
