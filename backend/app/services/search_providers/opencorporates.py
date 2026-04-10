"""
OpenCorporates Provider
========================
Searches OpenCorporates — the largest open database of companies in the world,
covering 200+ million companies across 140+ jurisdictions.

Invaluable for:
  - Corporate transparency research
  - Tracing shell companies and beneficial ownership
  - Connecting officers/directors across companies
  - Investigating offshore structures (LLCs, holding companies)
  - Following the money in political/lobbying research

No API key required for basic search (rate-limited to ~20 req/min).
Optional: set OPENCORPORATES_API_KEY for higher limits.
Docs: https://api.opencorporates.com/
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.opencorporates")


class OpenCorporatesProvider(BaseProvider):
    NAME = "OpenCorporates"
    ID = "opencorporates"
    SOURCE_TYPE = SourceType.ALTERNATIVE
    REQUIRES_KEY = False

    _COMPANY_URL = "https://api.opencorporates.com/v0.4/companies/search"
    _OFFICER_URL = "https://api.opencorporates.com/v0.4/officers/search"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        per_type = max(1, max_results // 2)

        headers = {**self._DEFAULT_HEADERS, "Accept": "application/json"}

        # Search companies
        try:
            params: dict = {
                "q": query,
                "per_page": per_type,
                "page": page,
                "format": "json",
            }
            if self._api_key:
                params["api_token"] = self._api_key

            resp = requests.get(
                self._COMPANY_URL, params=params, headers=headers, timeout=12
            )
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", {}).get("companies", []):
                co = item.get("company", {})
                name = co.get("name", "")
                cn = co.get("company_number", "")
                jur = co.get("jurisdiction_code", "")
                status = co.get("current_status", "")
                inc_date = co.get("incorporation_date", "")
                source_url = co.get("opencorporates_url", "")
                registered = co.get("registered_address_in_full", "")

                snippet_parts = []
                if jur:
                    snippet_parts.append(f"Jurisdiction: {jur.upper()}")
                if cn:
                    snippet_parts.append(f"No.: {cn}")
                if status:
                    snippet_parts.append(f"Status: {status}")
                if registered:
                    snippet_parts.append(f"Address: {registered}")

                results.append(
                    SearchResult(
                        title=name or cn,
                        url=source_url or f"https://opencorporates.com/companies/{jur}/{cn}",
                        snippet=" · ".join(snippet_parts),
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        published_at=inc_date or None,
                        extra={
                            "company_number": cn,
                            "jurisdiction": jur,
                            "status": status,
                            "type": "company",
                            "inactive": co.get("inactive", False),
                        },
                    )
                )
        except Exception as exc:
            logger.warning(f"OpenCorporates company search failed: {exc}")

        # Search officers/directors
        try:
            if len(results) < max_results:
                params = {
                    "q": query,
                    "per_page": per_type,
                    "page": page,
                    "format": "json",
                }
                if self._api_key:
                    params["api_token"] = self._api_key

                resp = requests.get(
                    self._OFFICER_URL, params=params, headers=headers, timeout=12
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("results", {}).get("officers", []):
                    off = item.get("officer", {})
                    name = off.get("name", "")
                    position = off.get("position", "")
                    source_url = off.get("opencorporates_url", "")
                    co = off.get("company", {})
                    co_name = co.get("name", "")
                    co_jur = co.get("jurisdiction_code", "")

                    results.append(
                        SearchResult(
                            title=f"{name} ({position})",
                            url=source_url or "https://opencorporates.com",
                            snippet=f"Officer/Director at {co_name} [{co_jur.upper() if co_jur else ''}]",
                            source=self.NAME,
                            source_id=self.ID,
                            source_type=self.SOURCE_TYPE,
                            published_at=off.get("start_date"),
                            extra={
                                "position": position,
                                "company": co_name,
                                "jurisdiction": co_jur,
                                "type": "officer",
                            },
                        )
                    )
        except Exception as exc:
            logger.warning(f"OpenCorporates officer search failed: {exc}")

        return results[:max_results]
