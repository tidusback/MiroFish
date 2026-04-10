"""
CourtListener Provider
======================
Searches CourtListener (RECAP/Free Law Project) — the largest free, open
database of US federal court opinions, dockets, and oral arguments.

Surfaces court cases, rulings, and legal documents that Google buries
under paywalled services like Westlaw and LexisNexis.

Covers:
  - US Supreme Court opinions
  - All federal circuit and district court opinions
  - PACER dockets (RECAP archive)
  - Oral arguments

No API key required (public API). Rate limit: 5,000 req/day per IP.
Docs: https://www.courtlistener.com/api/rest/v3/
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.courtlistener")


class CourtListenerProvider(BaseProvider):
    NAME = "CourtListener"
    ID = "courtlistener"
    SOURCE_TYPE = SourceType.ARCHIVE
    REQUIRES_KEY = False

    _OPINION_URL = "https://www.courtlistener.com/api/rest/v3/search/"
    _BASE = "https://www.courtlistener.com"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            params = {
                "q": query,
                "type": "o",           # opinions
                "order_by": "score desc",
                "format": "json",
                "page_size": max_results,
                "page": page,
            }
            headers = {
                **self._DEFAULT_HEADERS,
                "Accept": "application/json",
            }

            resp = requests.get(
                self._OPINION_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                absolute_url = item.get("absolute_url", "")
                url = (self._BASE + absolute_url) if absolute_url else ""
                if not url:
                    continue

                case_name = item.get("caseName", "")
                snippet = item.get("snippet", "") or ""
                # Strip highlight tags
                import re
                snippet = re.sub(r"</?mark>", "", snippet).strip()

                court = item.get("court", "") or item.get("court_citation_string", "")
                date_filed = item.get("dateFiled") or item.get("dateArgued")
                judges = item.get("judge", "")
                status = item.get("status", "")
                citations = item.get("citation", [])
                citation_str = ", ".join(citations) if citations else ""

                results.append(
                    SearchResult(
                        title=case_name or url,
                        url=url,
                        snippet=snippet[:500],
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        published_at=date_filed,
                        author=judges or None,
                        extra={
                            "court": court,
                            "status": status,
                            "citation": citation_str,
                            "type": "court_opinion",
                            "docket_number": item.get("docketNumber", ""),
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"CourtListener search failed: {exc}")

        return results
