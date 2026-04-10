"""
Semantic Scholar Provider
==========================
Academic paper search via Semantic Scholar's free public API.
Covers 200M+ papers across all disciplines.
Often surfaces research that contradicts the mainstream scientific consensus.

No API key required (public tier: 100 req/5 min).
Optional: set SEMANTIC_SCHOLAR_API_KEY for higher rate limits.
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.semantic_scholar")


class SemanticScholarProvider(BaseProvider):
    NAME = "Semantic Scholar"
    ID = "semantic_scholar"
    SOURCE_TYPE = SourceType.ACADEMIC
    REQUIRES_KEY = False

    _SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            offset = (page - 1) * max_results
            headers = {"Accept": "application/json"}
            if self._api_key:
                headers["x-api-key"] = self._api_key

            params = {
                "query": query,
                "limit": min(max_results, 100),
                "offset": offset,
                "fields": "title,abstract,authors,year,externalIds,openAccessPdf,venue,publicationDate",
            }

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            for paper in data.get("data", []):
                paper_id = paper.get("paperId", "")
                title = paper.get("title", "")
                abstract = paper.get("abstract", "") or ""

                # Prefer open-access PDF, fall back to Semantic Scholar page
                pdf_info = paper.get("openAccessPdf") or {}
                url = pdf_info.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"

                authors = [a.get("name", "") for a in paper.get("authors", [])]
                ids = paper.get("externalIds", {}) or {}
                doi = ids.get("DOI", "")
                arxiv_id = ids.get("ArXiv", "")

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=abstract[:500],
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                        published_at=paper.get("publicationDate") or (str(paper.get("year")) if paper.get("year") else None),
                        extra={
                            "venue": paper.get("venue", ""),
                            "doi": doi,
                            "arxiv_id": arxiv_id,
                            "open_access": bool(pdf_info),
                            "paper_id": paper_id,
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"Semantic Scholar search failed: {exc}")

        return results
