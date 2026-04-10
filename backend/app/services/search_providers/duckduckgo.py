"""
DuckDuckGo Provider
===================
Scrapes DuckDuckGo's ad-free HTML interface.
No API key required. Results are organic, no tracking.
"""

import logging
import time
from typing import List
from urllib.parse import unquote, urlparse, parse_qs

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.duckduckgo")


class DuckDuckGoProvider(BaseProvider):
    NAME = "DuckDuckGo"
    ID = "duckduckgo"
    SOURCE_TYPE = SourceType.WEB
    REQUIRES_KEY = False

    # POST to the HTML (lite) endpoint – no JS, no ads, no tracking pixels
    _URL = "https://html.duckduckgo.com/html/"

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
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": "https://html.duckduckgo.com/",
            }

            # Pagination: DuckDuckGo HTML uses an 's' offset param (multiples of 30)
            offset = (page - 1) * 30
            data = {"q": query, "b": "", "kl": "us-en"}
            if offset > 0:
                data["s"] = str(offset)
                data["dc"] = str(offset + 1)

            resp = requests.post(
                self._URL, data=data, headers=headers, timeout=15
            )
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            for div in soup.find_all("div", class_=lambda c: c and "result" in c.split()):
                # Skip ads (they have class "result--ad")
                cls = " ".join(div.get("class", []))
                if "result--ad" in cls or "result--more" in cls:
                    continue

                title_tag = div.find("a", class_="result__a")
                snippet_tag = div.find("a", class_="result__snippet") or div.find(
                    "div", class_="result__snippet"
                )

                if not title_tag:
                    continue

                title = title_tag.get_text(strip=True)

                # Extract real URL from DDG redirect href
                href = title_tag.get("href", "")
                url = _extract_real_url(href)
                if not url:
                    continue

                snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                    )
                )

                if len(results) >= max_results:
                    break

            time.sleep(0.3)

        except Exception as exc:
            logger.warning(f"DuckDuckGo search failed: {exc}")

        return results


def _extract_real_url(href: str) -> str:
    """Extract the real destination URL from a DuckDuckGo redirect href."""
    if not href:
        return ""
    if href.startswith("http") and "duckduckgo.com" not in href:
        return href
    try:
        # Handles /l/?uddg=... and //duckduckgo.com/l/?uddg=...
        if "uddg=" in href:
            parsed = urlparse(href if href.startswith("http") else "https://duckduckgo.com" + href)
            params = parse_qs(parsed.query)
            raw = params.get("uddg", [""])[0]
            return unquote(raw)
    except Exception:
        pass
    return ""
