"""
Uncensored Multi-Engine Search Service
=======================================
Aggregates results from multiple independent search engines and data sources
to break through mainstream filter bubbles. No ads, no personalisation, no
content suppression.

Engines (no API key required)
------------------------------
  DDG       – DuckDuckGo HTML endpoint (no tracking)
  Reddit    – Reddit public JSON search API
  arXiv     – Academic pre-prints (open-access)
  Archive   – Internet Archive full-text search (finds deleted/censored pages)
  Ahmia     – Surface-web index of Tor .onion sites
  GitHub    – Code & repository search

Engines (optional API key)
---------------------------
  Brave     – Brave Search API (significantly less filtered than Google/Bing)
  SearXNG   – Self-hosted meta-search instance
"""

import re
import time
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlencode, quote_plus

logger = logging.getLogger("mirofish.search")

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_engine: str
    source_label: str = ""
    published: Optional[str] = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source_engine": self.source_engine,
            "source_label": self.source_label,
            "published": self.published,
            "extra": self.extra,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_session():
    """Return a requests Session with a neutral User-Agent."""
    try:
        import requests
        s = requests.Session()
        s.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9",
        })
        return s
    except ImportError:
        raise RuntimeError("requests library not installed")


def _strip_html(text: str) -> str:
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(text, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", text).strip()


def _safe_get(session, url, *, params=None, timeout=12, **kwargs):
    try:
        r = session.get(url, params=params, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r
    except Exception as exc:
        logger.warning(f"GET {url} failed: {exc}")
        return None


def _safe_post(session, url, *, data=None, timeout=12, **kwargs):
    try:
        r = session.post(url, data=data, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r
    except Exception as exc:
        logger.warning(f"POST {url} failed: {exc}")
        return None


# ---------------------------------------------------------------------------
# Individual engine scrapers
# ---------------------------------------------------------------------------

def search_duckduckgo(query: str, max_results: int = 10) -> List[SearchResult]:
    """
    Scrape DuckDuckGo HTML endpoint – no personalisation, no ad injection
    in the scraped layer, no search history tracking.
    """
    session = _get_session()
    session.headers.update({
        "Accept": "text/html,application/xhtml+xml",
        "Referer": "https://duckduckgo.com/",
    })

    r = _safe_post(
        session,
        "https://html.duckduckgo.com/html/",
        data={"q": query, "b": "", "kl": "us-en"},
    )
    if not r:
        return []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
    except ImportError:
        logger.error("beautifulsoup4 / lxml not installed")
        return []

    results = []
    for div in soup.select(".result")[:max_results]:
        a_tag = div.select_one(".result__a")
        snippet_tag = div.select_one(".result__snippet")
        if not a_tag:
            continue
        title = a_tag.get_text(strip=True)
        href = a_tag.get("href", "")
        # DDG uses redirect URLs; extract the real URL
        if "uddg=" in href:
            try:
                from urllib.parse import parse_qs, urlparse
                qs = parse_qs(urlparse(href).query)
                href = qs.get("uddg", [href])[0]
            except Exception:
                pass
        snippet = snippet_tag.get_text(strip=True) if snippet_tag else ""
        results.append(SearchResult(
            title=title, url=href, snippet=snippet,
            source_engine="duckduckgo", source_label="DuckDuckGo",
        ))
    return results


def search_reddit(query: str, max_results: int = 10) -> List[SearchResult]:
    """
    Reddit public JSON search – surfaces community discussions, whistleblower
    threads, and crowdsourced investigative content.
    """
    session = _get_session()
    session.headers.update({"Accept": "application/json"})

    r = _safe_get(
        session,
        "https://www.reddit.com/search.json",
        params={"q": query, "limit": max_results, "sort": "relevance", "type": "link"},
    )
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    results = []
    for post in data.get("data", {}).get("children", []):
        p = post.get("data", {})
        title = p.get("title", "")
        url = p.get("url", "")
        selftext = p.get("selftext", "") or p.get("url", "")
        snippet = selftext[:300].replace("\n", " ").strip()
        subreddit = p.get("subreddit_name_prefixed", "")
        results.append(SearchResult(
            title=title, url=url, snippet=snippet,
            source_engine="reddit", source_label=f"Reddit {subreddit}",
            published=str(p.get("created_utc", "")),
            extra={"score": p.get("score", 0), "num_comments": p.get("num_comments", 0)},
        ))
    return results


def search_arxiv(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    arXiv open-access pre-print server – scientific research before/after
    peer-review, including suppressed or controversial findings.
    """
    session = _get_session()
    r = _safe_get(
        session,
        "https://export.arxiv.org/api/query",
        params={
            "search_query": f"all:{query}",
            "max_results": max_results,
            "sortBy": "relevance",
        },
    )
    if not r:
        return []

    results = []
    try:
        root = ET.fromstring(r.text)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for entry in root.findall("atom:entry", ns):
            title = (entry.findtext("atom:title", namespaces=ns) or "").strip()
            url = (entry.findtext("atom:id", namespaces=ns) or "").strip()
            summary = (entry.findtext("atom:summary", namespaces=ns) or "").replace("\n", " ").strip()[:400]
            published = (entry.findtext("atom:published", namespaces=ns) or "")[:10]
            authors = [a.findtext("atom:name", namespaces=ns) or "" for a in entry.findall("atom:author", ns)]
            results.append(SearchResult(
                title=title, url=url, snippet=summary,
                source_engine="arxiv", source_label="arXiv (Academic Pre-print)",
                published=published,
                extra={"authors": authors[:3]},
            ))
    except Exception as exc:
        logger.warning(f"arXiv parse error: {exc}")

    return results


def search_archive_org(query: str, max_results: int = 8) -> List[SearchResult]:
    """
    Internet Archive full-text search – recovers deleted, censored, and
    de-indexed web content. The Wayback Machine never forgets.
    """
    session = _get_session()
    r = _safe_get(
        session,
        "https://archive.org/advancedsearch.php",
        params={
            "q": query,
            "fl[]": ["identifier", "title", "description", "date", "subject"],
            "rows": max_results,
            "output": "json",
            "callback": "",
        },
    )
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    results = []
    for doc in data.get("response", {}).get("docs", []):
        identifier = doc.get("identifier", "")
        title = doc.get("title", identifier)
        if isinstance(title, list):
            title = title[0] if title else identifier
        desc = doc.get("description", "")
        if isinstance(desc, list):
            desc = " ".join(desc)
        snippet = str(desc)[:400].replace("\n", " ").strip()
        url = f"https://archive.org/details/{identifier}"
        published = str(doc.get("date", ""))[:10]
        results.append(SearchResult(
            title=str(title), url=url, snippet=snippet,
            source_engine="archive_org", source_label="Internet Archive",
            published=published,
        ))
    return results


def search_ahmia(query: str, max_results: int = 8) -> List[SearchResult]:
    """
    Ahmia – surface-web search index of Tor .onion hidden services.
    Surfaces content that exists outside the indexed clearnet.
    """
    session = _get_session()
    r = _safe_get(
        session,
        "https://ahmia.fi/search/",
        params={"q": query},
    )
    if not r:
        return []

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(r.text, "lxml")
    except ImportError:
        return []

    results = []
    for item in soup.select(".result")[:max_results]:
        h4 = item.select_one("h4")
        a_tag = item.select_one("a[href]")
        p_tag = item.select_one("p")
        if not (h4 and a_tag):
            continue
        title = h4.get_text(strip=True)
        url = a_tag["href"]
        snippet = p_tag.get_text(strip=True) if p_tag else ""
        results.append(SearchResult(
            title=title, url=url, snippet=snippet,
            source_engine="ahmia", source_label="Ahmia (Tor Index)",
        ))
    return results


def search_github(query: str, max_results: int = 5) -> List[SearchResult]:
    """
    GitHub repository and code search – surfaces leaked data, shadow-banned
    repos, whistleblower code dumps, and raw technical documents.
    """
    session = _get_session()
    session.headers.update({"Accept": "application/vnd.github+json"})

    r = _safe_get(
        session,
        "https://api.github.com/search/repositories",
        params={"q": query, "per_page": max_results, "sort": "best-match"},
    )
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    results = []
    for repo in data.get("items", [])[:max_results]:
        title = repo.get("full_name", "")
        url = repo.get("html_url", "")
        snippet = repo.get("description", "") or ""
        topics = repo.get("topics", [])
        if topics:
            snippet += f" [Topics: {', '.join(topics[:5])}]"
        results.append(SearchResult(
            title=title, url=url, snippet=snippet.strip(),
            source_engine="github", source_label="GitHub",
            published=str(repo.get("updated_at", ""))[:10],
            extra={"stars": repo.get("stargazers_count", 0), "language": repo.get("language", "")},
        ))
    return results


def search_brave(query: str, api_key: str, max_results: int = 10) -> List[SearchResult]:
    """
    Brave Search API – independent index built without Google/Bing data.
    Significantly less editorial filtering than mainstream engines.
    """
    session = _get_session()
    session.headers.update({
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    })

    r = _safe_get(
        session,
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max_results},
    )
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    results = []
    for item in data.get("web", {}).get("results", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("description", ""),
            source_engine="brave", source_label="Brave Search",
            published=item.get("page_age", ""),
            extra={"age": item.get("age", "")},
        ))
    return results


def search_searxng(query: str, instance_url: str, max_results: int = 10) -> List[SearchResult]:
    """
    SearXNG – self-hosted meta-search that queries many engines simultaneously
    without logging queries or returning personalised results.
    """
    session = _get_session()
    session.headers.update({"Accept": "application/json"})

    r = _safe_get(
        session,
        f"{instance_url.rstrip('/')}/search",
        params={"q": query, "format": "json", "pageno": 1},
    )
    if not r:
        return []

    try:
        data = r.json()
    except Exception:
        return []

    results = []
    for item in data.get("results", [])[:max_results]:
        results.append(SearchResult(
            title=item.get("title", ""),
            url=item.get("url", ""),
            snippet=item.get("content", ""),
            source_engine="searxng", source_label="SearXNG",
            published=item.get("publishedDate", ""),
            extra={"engines": item.get("engines", [])},
        ))
    return results


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

class SearchAggregator:
    """
    Run multiple engines in parallel (via threads) and merge results,
    deduplicating by URL.
    """

    def __init__(self, brave_api_key: str = "", searxng_url: str = ""):
        self.brave_api_key = brave_api_key
        self.searxng_url = searxng_url

    def search(
        self,
        query: str,
        engines: Optional[List[str]] = None,
        max_per_engine: int = 8,
    ) -> dict:
        """
        Run search across selected engines and return aggregated results.

        Args:
            query:           Search query string
            engines:         List of engine names to use, or None for all available
            max_per_engine:  Max results per engine

        Returns:
            dict with keys: results, total, engines_used, engines_failed
        """
        import concurrent.futures

        available = {
            "duckduckgo": lambda q, n: search_duckduckgo(q, n),
            "reddit": lambda q, n: search_reddit(q, n),
            "arxiv": lambda q, n: search_arxiv(q, n),
            "archive": lambda q, n: search_archive_org(q, n),
            "ahmia": lambda q, n: search_ahmia(q, n),
            "github": lambda q, n: search_github(q, n),
        }

        if self.brave_api_key:
            available["brave"] = lambda q, n: search_brave(q, self.brave_api_key, n)
        if self.searxng_url:
            available["searxng"] = lambda q, n: search_searxng(q, self.searxng_url, n)

        to_run = {k: v for k, v in available.items()
                  if engines is None or k in engines}

        all_results: List[SearchResult] = []
        engines_used = []
        engines_failed = []
        seen_urls = set()

        def run_engine(name, fn):
            try:
                res = fn(query, max_per_engine)
                logger.info(f"Engine '{name}' returned {len(res)} results for: {query!r}")
                return name, res, None
            except Exception as exc:
                logger.warning(f"Engine '{name}' failed: {exc}")
                return name, [], str(exc)

        with concurrent.futures.ThreadPoolExecutor(max_workers=len(to_run)) as pool:
            futures = {pool.submit(run_engine, name, fn): name for name, fn in to_run.items()}
            for future in concurrent.futures.as_completed(futures):
                name, results, err = future.result()
                if err:
                    engines_failed.append({"engine": name, "error": err})
                else:
                    engines_used.append(name)
                for r in results:
                    if r.url and r.url not in seen_urls:
                        seen_urls.add(r.url)
                        all_results.append(r)

        return {
            "results": [r.to_dict() for r in all_results],
            "total": len(all_results),
            "engines_used": engines_used,
            "engines_failed": engines_failed,
            "query": query,
        }

    def deep_search(self, query: str, max_per_engine: int = 10) -> dict:
        """
        Deep search using all available engines including dark-web index (Ahmia)
        and archive sources. Use for finding buried/censored content.
        """
        return self.search(query, engines=None, max_per_engine=max_per_engine)

    def available_engines(self) -> List[dict]:
        engines = [
            {
                "id": "duckduckgo",
                "name": "DuckDuckGo",
                "description": "No-tracking search. No personalisation, no ad-based result manipulation.",
                "requires_key": False,
                "category": "general",
            },
            {
                "id": "reddit",
                "name": "Reddit",
                "description": "Community discussions, whistleblower threads, and crowdsourced investigations.",
                "requires_key": False,
                "category": "social",
            },
            {
                "id": "arxiv",
                "name": "arXiv",
                "description": "Open-access scientific pre-prints, including suppressed or controversial findings.",
                "requires_key": False,
                "category": "academic",
            },
            {
                "id": "archive",
                "name": "Internet Archive",
                "description": "Recovers deleted, de-indexed, and censored web content. The web never forgets.",
                "requires_key": False,
                "category": "deep",
            },
            {
                "id": "ahmia",
                "name": "Ahmia (Tor Index)",
                "description": "Surface-web search index of Tor .onion hidden services.",
                "requires_key": False,
                "category": "deep",
            },
            {
                "id": "github",
                "name": "GitHub",
                "description": "Code repos, leaked data, whistleblower dumps, and raw technical documents.",
                "requires_key": False,
                "category": "technical",
            },
        ]

        if self.brave_api_key:
            engines.append({
                "id": "brave",
                "name": "Brave Search",
                "description": "Independent index – not derived from Google/Bing. Less editorial filtering.",
                "requires_key": True,
                "category": "general",
                "active": True,
            })
        if self.searxng_url:
            engines.append({
                "id": "searxng",
                "name": "SearXNG",
                "description": "Self-hosted meta-search over dozens of engines. No logging.",
                "requires_key": True,
                "category": "general",
                "active": True,
            })

        return engines
