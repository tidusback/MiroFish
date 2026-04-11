"""
DocumentCloud Provider
=======================
Searches DocumentCloud — the primary archive for FOIA-obtained government
documents, leaked records, and investigative journalism source material.

Used by major newsrooms (NYT, ProPublica, BuzzFeed News, The Intercept)
to publish primary source documents. Hundreds of thousands of public records,
whistleblower disclosures, court filings, and leaked corporate memos.

No API key required for public document search.
Docs: https://www.documentcloud.org/help/api
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.documentcloud")


class DocumentCloudProvider(BaseProvider):
    NAME = "DocumentCloud"
    ID = "documentcloud"
    SOURCE_TYPE = SourceType.ARCHIVE
    REQUIRES_KEY = False

    _SEARCH_URL = "https://api.www.documentcloud.org/api/documents/search/"

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
                "per_page": max_results,
                "page": page,
                "expand": "user,organization",
            }
            headers = {**self._DEFAULT_HEADERS, "Accept": "application/json"}

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            for doc in data.get("results", []):
                doc_id = doc.get("id", "")
                slug = doc.get("slug", "")
                title = doc.get("title", "")
                description = doc.get("description", "") or ""
                canonical_url = doc.get("canonical_url", "") or f"https://www.documentcloud.org/documents/{doc_id}-{slug}"

                # Source / uploader
                user = doc.get("user", {}) or {}
                org  = doc.get("organization", {}) or {}
                author = user.get("name") or user.get("username") or None
                org_name = org.get("name", "")
                if org_name and author:
                    author = f"{author} / {org_name}"

                pages = doc.get("page_count", 0)
                created = doc.get("created_at", "")
                access = doc.get("access", "public")
                language = doc.get("language", "")

                snippet_parts = [description[:300]] if description else []
                if pages:
                    snippet_parts.append(f"{pages} pages")
                if access != "public":
                    snippet_parts.append(f"Access: {access}")

                results.append(
                    SearchResult(
                        title=title or slug or doc_id,
                        url=canonical_url,
                        snippet=" · ".join(p for p in snippet_parts if p),
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=author,
                        published_at=created or None,
                        extra={
                            "page_count": pages,
                            "language": language,
                            "access": access,
                            "organization": org_name,
                            "type": "foia_document",
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"DocumentCloud search failed: {exc}")

        return results
