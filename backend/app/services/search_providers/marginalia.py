"""
Marginalia Search Provider
==========================
Marginalia.nu is an independent, non-commercial search engine that deliberately
prioritizes non-commercial, text-heavy, non-SEO-optimized websites.

It finds the parts of the internet that Google has buried under ads and
SEO-farmed content: old forums, personal blogs, technical documentation,
and niche communities.

API: https://marginalia-search.com/explore
No API key required.
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.marginalia")


class MarginaliaProvider(BaseProvider):
    NAME = "Marginalia"
    ID = "marginalia"
    SOURCE_TYPE = SourceType.ALTERNATIVE
    REQUIRES_KEY = False

    _API_URL = "https://api.marginalia.nu/api/search/{query}"
    _PUBLIC_API_URL = "https://api.marginalia.nu/api/public/search/{query}"

    def __init__(self, api_key: str = ""):
        self._api_key = api_key

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
            from urllib.parse import quote
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            encoded = quote(query)
            if self._api_key:
                url = self._API_URL.format(query=encoded)
            else:
                url = self._PUBLIC_API_URL.format(query=encoded)

            headers = {
                **self._DEFAULT_HEADERS,
                "Accept": "application/json",
            }
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"

            params = {
                "index": 0,  # profile: 0=default, 1=forum, 2=vintage, 3=academia
                "count": min(max_results, 100),
                "start": (page - 1) * max_results,
            }

            resp = requests.get(url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            for item in data.get("results", []):
                title = item.get("title") or item.get("url", "")
                desc = item.get("description", "")
                item_url = item.get("url", "")
                quality = item.get("quality", 0)

                results.append(
                    SearchResult(
                        title=title,
                        url=item_url,
                        snippet=desc,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        extra={
                            "quality": quality,
                            "features": item.get("features", []),
                        },
                    )
                )

                if len(results) >= max_results:
                    break

        except Exception as exc:
            logger.warning(f"Marginalia search failed: {exc}")

        return results
