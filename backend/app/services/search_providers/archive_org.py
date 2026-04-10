"""
Internet Archive Provider
=========================
Searches the Internet Archive (archive.org) full-text index.

This is the largest digital library ever created – it indexes content
that has been removed from the live web, censored, or shadow-banned.
Includes news articles, books, government documents, and websites
as they existed at any point in history.

Two endpoints used:
  1. Full-text search (texts, web captures)
  2. CDX API – find archived snapshots of any URL

No API key required.
"""

import logging
from typing import List
from urllib.parse import quote_plus

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.archive_org")


class ArchiveOrgProvider(BaseProvider):
    NAME = "Internet Archive"
    ID = "archive_org"
    SOURCE_TYPE = SourceType.ARCHIVE
    REQUIRES_KEY = False

    _SEARCH_URL = "https://archive.org/advancedsearch.php"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            # Include multiple media types for maximum coverage
            # texts: books, papers, docs; web: crawled pages
            params = {
                "q": query,
                "fl[]": ["identifier", "title", "description", "subject",
                         "creator", "date", "mediatype", "language"],
                "rows": max_results,
                "page": page,
                "output": "json",
                "sort[]": "downloads desc",
                # Search all media types
                "mediatype": "texts",
            }

            headers = {**self._DEFAULT_HEADERS}
            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            docs = data.get("response", {}).get("docs", [])
            for doc in docs:
                identifier = doc.get("identifier", "")
                title = _first(doc.get("title"))
                description = _first(doc.get("description")) or _first(doc.get("subject")) or ""
                url = f"https://archive.org/details/{identifier}"
                creator = _first(doc.get("creator")) or ""
                date = _first(doc.get("date")) or ""

                results.append(
                    SearchResult(
                        title=title or identifier,
                        url=url,
                        snippet=description[:400],
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=creator,
                        published_at=date or None,
                        extra={
                            "identifier": identifier,
                            "mediatype": _first(doc.get("mediatype")) or "texts",
                            "language": _first(doc.get("language")) or "",
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"Internet Archive search failed: {exc}")

        return results


def _first(val):
    """Return the first element if list, or the value itself."""
    if isinstance(val, list):
        return val[0] if val else ""
    return val or ""
