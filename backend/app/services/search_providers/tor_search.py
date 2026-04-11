"""
Tor Search Provider (Direct .onion access)
==========================================
Searches the Tor dark web directly through a SOCKS5 proxy, bypassing
the Ahmia clearnet index to query .onion search engines natively.

Requires Tor to be running locally (default: socks5h://127.0.0.1:9050).
Silently returns empty results if Tor is not available.

Searches two .onion search engines in parallel:
  - Haystack  – largest Tor full-text index
  - Torch     – oldest Tor search engine

Override the proxy with TOR_SOCKS_PROXY env var:
  TOR_SOCKS_PROXY=socks5h://127.0.0.1:9050

Note: `requests[socks]` must be installed (PySocks dependency).
      Run: pip install requests[socks]
"""

import logging
import os
import re
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.tor_direct")

_TOR_PROXY = os.environ.get("TOR_SOCKS_PROXY", "socks5h://127.0.0.1:9050")

# .onion search engine URLs
_HAYSTACK_URL = "http://haystak5njsmn2hqkewecpaxetahtwhsbsa64jom2k22z5afxhnpxfid.onion/"
_TORCH_URL = "http://torchdeedp3i2jigzjdmfpn5ttjhthh5wbmda2rr3jvqjg5p77c54dqd.onion/search"


class TorSearchProvider(BaseProvider):
    NAME = "Tor Search (Direct)"
    ID = "tor_direct"
    SOURCE_TYPE = SourceType.DARKWEB
    REQUIRES_KEY = False

    def is_available(self) -> bool:
        """Check if Tor SOCKS5 proxy is reachable."""
        return _tor_available()

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        if not _tor_available():
            return []

        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []

        # Try Haystack
        try:
            results.extend(_search_haystack(query, max_results // 2 + 1, page, requests))
        except Exception as exc:
            logger.debug(f"Haystack search failed: {exc}")

        # Try Torch if we need more results
        if len(results) < max_results:
            try:
                results.extend(_search_torch(query, max_results - len(results), page, requests))
            except Exception as exc:
                logger.debug(f"Torch search failed: {exc}")

        return results[:max_results]


# ── helpers ───────────────────────────────────────────────────────────────────

def _proxied_session(requests_mod):
    """Return a requests Session routed through the Tor SOCKS5 proxy."""
    s = requests_mod.Session()
    s.proxies = {
        "http":  _TOR_PROXY,
        "https": _TOR_PROXY,
    }
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/109.0",
    })
    return s


def _tor_available() -> bool:
    """Quick TCP check to see if the Tor SOCKS5 port is open."""
    try:
        import socket
        from urllib.parse import urlparse
        parsed = urlparse(_TOR_PROXY)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 9050
        with socket.create_connection((host, port), timeout=2):
            return True
    except Exception:
        return False


def _search_haystack(query: str, max_results: int, page: int, req) -> List[SearchResult]:
    """Search Haystack .onion search engine."""
    from bs4 import BeautifulSoup
    session = _proxied_session(req)
    params = {"q": query, "offset": (page - 1) * max_results}
    resp = session.get(_HAYSTACK_URL, params=params, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    for item in soup.find_all("li", class_=re.compile(r"result|item", re.I)):
        a = item.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a["href"]
        if not href.startswith("http"):
            continue

        desc_el = item.find("p") or item.find("span", class_=re.compile(r"desc|snippet", re.I))
        snippet = desc_el.get_text(strip=True) if desc_el else ""

        results.append(SearchResult(
            title=title or href,
            url=href,
            snippet=snippet[:400],
            source="Haystack (Tor)",
            source_id="tor_direct",
            source_type=SourceType.DARKWEB,
            extra={"engine": "haystack", "note": "Direct Tor access"},
        ))
        if len(results) >= max_results:
            break

    return results


def _search_torch(query: str, max_results: int, page: int, req) -> List[SearchResult]:
    """Search Torch .onion search engine."""
    from bs4 import BeautifulSoup
    session = _proxied_session(req)
    params = {"query": query, "action": "search", "page": page}
    resp = session.get(_TORCH_URL, params=params, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    for dt in soup.find_all("dt"):
        a = dt.find("a", href=True)
        if not a:
            continue
        title = a.get_text(strip=True)
        href = a["href"]
        if not href.startswith("http"):
            continue

        dd = dt.find_next_sibling("dd")
        snippet = dd.get_text(strip=True) if dd else ""

        results.append(SearchResult(
            title=title or href,
            url=href,
            snippet=snippet[:400],
            source="Torch (Tor)",
            source_id="tor_direct",
            source_type=SourceType.DARKWEB,
            extra={"engine": "torch", "note": "Direct Tor access"},
        ))
        if len(results) >= max_results:
            break

    return results
