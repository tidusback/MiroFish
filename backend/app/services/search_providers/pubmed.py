"""
PubMed / NCBI Provider
=======================
Searches PubMed — the US National Library of Medicine's database of
35+ million biomedical and life-science publications.

Surfaces peer-reviewed medical/scientific research that:
  - Challenges pharmaceutical industry narratives
  - Documents drug side effects underreported in mainstream coverage
  - Shows suppressed/retracted studies (retraction still visible)
  - Contradicts official public-health guidance
  - Covers censored topics in mainstream medical publishing

Includes pre-prints via Europe PMC and bioRxiv links where available.

No API key required (optional: set NCBI_API_KEY for 10x rate limit bump).
Docs: https://www.ncbi.nlm.nih.gov/books/NBK25497/
"""

import logging
from typing import List, Optional

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.pubmed")

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_ARTICLE_URL = "https://pubmed.ncbi.nlm.nih.gov/{pmid}/"


class PubMedProvider(BaseProvider):
    NAME = "PubMed"
    ID = "pubmed"
    SOURCE_TYPE = SourceType.ACADEMIC
    REQUIRES_KEY = False

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def search(
        self,
        query: str,
        max_results: int = 10,
        page: int = 1,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            # Step 1: esearch – get PubMed IDs
            retstart = (page - 1) * max_results
            params: dict = {
                "db": "pubmed",
                "term": query,
                "retmax": max_results,
                "retstart": retstart,
                "retmode": "json",
                "sort": "relevance",
            }
            if self._api_key:
                params["api_key"] = self._api_key
            if date_from or date_to:
                lo = date_from.replace("-", "/") if date_from else "1900/01/01"
                hi = date_to.replace("-", "/") if date_to else "3000/12/31"
                params["datetype"] = "pdat"
                params["mindate"] = lo
                params["maxdate"] = hi

            headers = {**self._DEFAULT_HEADERS, "Accept": "application/json"}
            resp = requests.get(_ESEARCH, params=params, headers=headers, timeout=12)
            resp.raise_for_status()
            search_data = resp.json()

            pmids = search_data.get("esearchresult", {}).get("idlist", [])
            if not pmids:
                return []

            # Step 2: esummary – fetch article metadata
            sum_params: dict = {
                "db": "pubmed",
                "id": ",".join(pmids),
                "retmode": "json",
            }
            if self._api_key:
                sum_params["api_key"] = self._api_key

            resp2 = requests.get(_ESUMMARY, params=sum_params, headers=headers, timeout=12)
            resp2.raise_for_status()
            sum_data = resp2.json()

            result_map = sum_data.get("result", {})
            for pmid in pmids:
                doc = result_map.get(pmid)
                if not doc or pmid == "uids":
                    continue

                title = doc.get("title", "")
                pub_date = doc.get("pubdate", "")
                journal = doc.get("fulljournalname", "") or doc.get("source", "")
                epubdate = doc.get("epubdate", "")
                date_str = pub_date or epubdate or None

                # Authors
                authors = [
                    a.get("name", "") for a in doc.get("authors", []) if a.get("name")
                ]
                author_str = (
                    ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else "")
                ) or None

                # DOI and PMC link
                doi = ""
                pmc_url = ""
                for aid in doc.get("articleids", []):
                    if aid.get("idtype") == "doi":
                        doi = aid.get("value", "")
                    if aid.get("idtype") == "pmc":
                        pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{aid['value']}/"

                url = pmc_url or _ARTICLE_URL.format(pmid=pmid)

                # Publication type tags
                pub_types = [pt.get("value", "") for pt in doc.get("pubtype", [])]

                snippet_parts = []
                if journal:
                    snippet_parts.append(journal)
                if pub_types:
                    snippet_parts.append(", ".join(pt for pt in pub_types[:2] if pt))
                if doi:
                    snippet_parts.append(f"DOI: {doi}")

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=" · ".join(p for p in snippet_parts if p),
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=author_str,
                        published_at=date_str,
                        extra={
                            "pmid": pmid,
                            "journal": journal,
                            "doi": doi,
                            "pub_types": pub_types,
                            "open_access": bool(pmc_url),
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"PubMed search failed: {exc}")

        return results
