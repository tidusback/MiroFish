"""
Ahmia Dark Web Provider
========================
Searches Ahmia.fi — the most widely-used public index of Tor (.onion) sites.
Ahmia is accessible from the regular internet (clearnet) without needing Tor,
making it safe to query directly.

Used by security researchers, investigative journalists, and privacy advocates
to find information that exists only on the Tor network.

Ahmia actively removes child abuse material from its index.
All other content is surfaced without censorship.

No API key required. Results link to .onion addresses.
"""

import logging
import re
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.ahmia")


class AhmiaProvider(BaseProvider):
    NAME = "Ahmia (Dark Web)"
    ID = "ahmia"
    SOURCE_TYPE = SourceType.DARKWEB
    REQUIRES_KEY = False

    # Clearnet URL – no Tor required
    _SEARCH_URL = "https://ahmia.fi/search/"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            logger.error("requests/beautifulsoup4 not installed")
            return []

        results: List[SearchResult] = []
        try:
            headers = {
                **self._DEFAULT_HEADERS,
                "Referer": "https://ahmia.fi/",
            }
            params = {
                "q": query,
                "page": page - 1,  # Ahmia uses 0-based page
            }

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=20
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            for li in soup.find_all("li", class_="result"):
                title_tag = li.find("h4") or li.find("a")
                link_tag = li.find("a", href=True)
                desc_tag = li.find("p") or li.find("cite")

                if not title_tag or not link_tag:
                    continue

                title = title_tag.get_text(strip=True)
                href = link_tag.get("href", "")

                # Ahmia links go through their redirect: /redirect?service=http://...onion/...
                # Extract the real .onion URL
                onion_url = _extract_onion_url(href)

                # Also build a clearnet Ahmia redirect link as fallback
                if not onion_url:
                    onion_url = href if href.startswith("http") else f"https://ahmia.fi{href}"

                snippet = desc_tag.get_text(strip=True) if desc_tag else ""

                results.append(
                    SearchResult(
                        title=title,
                        url=onion_url,
                        snippet=snippet[:400],
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        extra={
                            "note": "Tor .onion address – requires Tor Browser to open directly",
                            "clearnet_redirect": f"https://ahmia.fi{href}" if not href.startswith("http") else href,
                        },
                    )
                )

                if len(results) >= max_results:
                    break

        except Exception as exc:
            logger.warning(f"Ahmia search failed: {exc}")

        return results


def _extract_onion_url(href: str) -> str:
    """Extract .onion URL from an Ahmia redirect link."""
    # Pattern: /redirect?service=http://xxxxx.onion/path
    match = re.search(r"service=(http[^&]+)", href)
    if match:
        from urllib.parse import unquote
        return unquote(match.group(1))
    # Direct .onion URL in href
    if ".onion" in href:
        return href
    return ""
