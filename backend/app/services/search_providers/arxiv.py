"""
arXiv Provider
==============
Searches arXiv.org pre-print repository via their official API.
Surfaces cutting-edge research — often published before (or instead of)
peer-reviewed journals, bypassing paywalls and editorial gatekeeping.

Covers: Physics, Math, CS, Biology, Economics, Finance, and more.
No API key required.
"""

import logging
from typing import List
from xml.etree import ElementTree as ET

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.arxiv")

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


class ArxivProvider(BaseProvider):
    NAME = "arXiv"
    ID = "arxiv"
    SOURCE_TYPE = SourceType.ACADEMIC
    REQUIRES_KEY = False

    _API_URL = "http://export.arxiv.org/api/query"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            start = (page - 1) * max_results
            params = {
                "search_query": f"all:{query}",
                "start": start,
                "max_results": max_results,
                "sortBy": "relevance",
                "sortOrder": "descending",
            }

            resp = requests.get(self._API_URL, params=params, timeout=15)
            resp.raise_for_status()

            root = ET.fromstring(resp.text)

            for entry in root.findall("atom:entry", _NS):
                title = _text(entry, "atom:title")
                summary = _text(entry, "atom:summary")
                arxiv_id = _text(entry, "atom:id")

                # Prefer the PDF link
                url = arxiv_id
                for link in entry.findall("atom:link", _NS):
                    if link.get("title") == "pdf":
                        url = link.get("href", arxiv_id)
                        break
                    if link.get("rel") == "alternate":
                        url = link.get("href", arxiv_id)

                authors = [
                    _text(a, "atom:name")
                    for a in entry.findall("atom:author", _NS)
                ]

                # arXiv categories (e.g. cs.AI, physics.hep-th)
                categories = [
                    c.get("term", "")
                    for c in entry.findall("arxiv:primary_category", _NS)
                ]
                categories += [
                    c.get("term", "")
                    for c in entry.findall("atom:category", _NS)
                ]
                categories = list(dict.fromkeys(filter(None, categories)))[:5]

                published = _text(entry, "atom:published")
                doi = _text(entry, "arxiv:doi")
                journal = _text(entry, "arxiv:journal_ref")

                results.append(
                    SearchResult(
                        title=title.replace("\n", " ").strip(),
                        url=url,
                        snippet=summary.replace("\n", " ").strip()[:500],
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                        published_at=published,
                        extra={
                            "categories": categories,
                            "doi": doi,
                            "journal_ref": journal,
                            "arxiv_id": arxiv_id,
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"arXiv search failed: {exc}")

        return results


def _text(el, tag: str) -> str:
    child = el.find(tag, _NS)
    return (child.text or "").strip() if child is not None else ""
