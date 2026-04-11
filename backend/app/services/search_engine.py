"""
MiroFish Uncensored Meta-Search Engine
=======================================
Aggregates results from 19 diverse sources in parallel:

  Web:           DuckDuckGo (no ads, scraping), Brave Search (independent index)
  Social:        Reddit, Hacker News, Mastodon (Fediverse, no censorship)
  Academic:      arXiv (preprints), Semantic Scholar (200M+ papers),
                 PubMed (35M+ biomedical papers)
  Archive:       Internet Archive, CourtListener (US federal courts),
                 DocumentCloud (FOIA / leaked documents)
  Dark Web:      Ahmia.fi (Tor .onion index, clearnet),
                 Tor Search (direct .onion access if Tor is running)
  Alternative:   Marginalia (non-commercial), GDELT (global news), Alt-News RSS,
                 OpenCorporates (corporate transparency)
  Encyclopedia:  Wikipedia
  Code:          GitHub

Features:
  - Parallel fan-out (ThreadPoolExecutor)
  - In-memory LRU result cache with configurable TTL (default 5 min)
  - Date-range filtering passed to providers that support it
  - URL deduplication + source interleaving
  - Graceful per-provider timeout (25 s)
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, List, Optional

from .search_providers import (
    AhmiaProvider,
    AlternativeNewsProvider,
    ArxivProvider,
    ArchiveOrgProvider,
    BaseProvider,
    BraveSearchProvider,
    CourtListenerProvider,
    DocumentCloudProvider,
    DuckDuckGoProvider,
    GDELTProvider,
    GitHubProvider,
    HackerNewsProvider,
    MarginaliaProvider,
    MastodonProvider,
    OpenCorporatesProvider,
    PubMedProvider,
    RedditProvider,
    SearchResult,
    SemanticScholarProvider,
    TorSearchProvider,
    WikipediaProvider,
)

logger = logging.getLogger("mirofish.search_engine")

# ── Provider registry ─────────────────────────────────────────────────────────

_PROVIDER_REGISTRY: Dict[str, type] = {
    "duckduckgo":       DuckDuckGoProvider,
    "brave":            BraveSearchProvider,
    "hackernews":       HackerNewsProvider,
    "reddit":           RedditProvider,
    "mastodon":         MastodonProvider,
    "wikipedia":        WikipediaProvider,
    "arxiv":            ArxivProvider,
    "semantic_scholar": SemanticScholarProvider,
    "pubmed":           PubMedProvider,
    "archive_org":      ArchiveOrgProvider,
    "courtlistener":    CourtListenerProvider,
    "documentcloud":    DocumentCloudProvider,
    "ahmia":            AhmiaProvider,
    "tor_direct":       TorSearchProvider,
    "marginalia":       MarginaliaProvider,
    "gdelt":            GDELTProvider,
    "alt_news":         AlternativeNewsProvider,
    "opencorporates":   OpenCorporatesProvider,
    "github":           GitHubProvider,
}

# Default set: free providers, no key required, responsive
DEFAULT_PROVIDERS = [
    "duckduckgo",
    "hackernews",
    "reddit",
    "mastodon",
    "wikipedia",
    "arxiv",
    "archive_org",
    "marginalia",
    "gdelt",
    "alt_news",
]

# Deep set: everything — dark web, courts, FOIA, medical, corporate, Tor
DEEP_PROVIDERS = DEFAULT_PROVIDERS + [
    "pubmed",
    "documentcloud",
    "courtlistener",
    "ahmia",
    "tor_direct",
    "semantic_scholar",
    "github",
    "opencorporates",
]

# ── Simple LRU result cache ───────────────────────────────────────────────────

class _LRUCache:
    """Thread-safe LRU cache with TTL."""

    def __init__(self, max_size: int = 200, ttl_secs: float = 300.0):
        self._cache: OrderedDict = OrderedDict()
        self._max = max_size
        self._ttl = ttl_secs
        import threading
        self._lock = threading.Lock()

    def _key(self, query: str, providers: List[str], max_per: int, page: int,
             date_from: Optional[str], date_to: Optional[str]) -> str:
        raw = json.dumps(
            {"q": query, "p": sorted(providers), "m": max_per,
             "pg": page, "df": date_from, "dt": date_to},
            sort_keys=True,
        )
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            ts, data = entry
            if time.monotonic() - ts > self._ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return data

    def put(self, key: str, data: dict) -> None:
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (time.monotonic(), data)
            while len(self._cache) > self._max:
                self._cache.popitem(last=False)

    def make_key(self, *args, **kwargs) -> str:
        return self._key(*args, **kwargs)


# ── Search engine ─────────────────────────────────────────────────────────────

class SearchEngine:
    """
    Parallel meta-search aggregator with caching.

    Usage:
        engine = SearchEngine.from_config(app_config)
        result = engine.search("your query", providers=DEEP_PROVIDERS)
    """

    def __init__(
        self,
        providers: Dict[str, BaseProvider],
        cache_ttl: float = 300.0,
        cache_size: int = 200,
    ):
        self._providers = providers
        self._cache = _LRUCache(max_size=cache_size, ttl_secs=cache_ttl)

    # ── Factory ───────────────────────────────────────────────────────────────

    @classmethod
    def from_config(cls, config) -> "SearchEngine":
        """Build the engine from Flask app config (reads API keys from env)."""
        providers: Dict[str, BaseProvider] = {}

        brave_key    = getattr(config, "BRAVE_SEARCH_API_KEY", "") or ""
        ss_key       = getattr(config, "SEMANTIC_SCHOLAR_API_KEY", "") or ""
        github_token = getattr(config, "GITHUB_TOKEN", "") or ""
        mar_key      = getattr(config, "MARGINALIA_API_KEY", "") or ""
        oc_key       = getattr(config, "OPENCORPORATES_API_KEY", "") or ""
        ncbi_key     = getattr(config, "NCBI_API_KEY", "") or ""
        cache_ttl    = float(getattr(config, "SEARCH_CACHE_TTL", 300))

        for pid, cls_ref in _PROVIDER_REGISTRY.items():
            try:
                if pid == "brave":
                    instance = BraveSearchProvider(api_key=brave_key)
                elif pid == "semantic_scholar":
                    instance = SemanticScholarProvider(api_key=ss_key)
                elif pid == "pubmed":
                    instance = PubMedProvider(api_key=ncbi_key)
                elif pid == "github":
                    instance = GitHubProvider(token=github_token)
                elif pid == "marginalia":
                    instance = MarginaliaProvider(api_key=mar_key)
                elif pid == "opencorporates":
                    instance = OpenCorporatesProvider(api_key=oc_key)
                else:
                    instance = cls_ref()
                providers[pid] = instance
            except Exception as exc:
                logger.warning(f"Failed to init provider {pid}: {exc}")

        return cls(providers, cache_ttl=cache_ttl)

    # ── Search ────────────────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        max_per_provider: int = 10,
        page: int = 1,
        timeout_secs: float = 25.0,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        use_cache: bool = True,
    ) -> dict:
        """
        Run a parallel search across all requested providers.

        Args:
            query:            Search query string
            providers:        Provider IDs to use (defaults to DEFAULT_PROVIDERS)
            max_per_provider: Max results per provider (1-50)
            page:             Page number (1-based)
            timeout_secs:     Per-provider wall-clock timeout
            date_from:        ISO date lower bound (YYYY-MM-DD), passed to providers
                              that support it (GDELT, arXiv, Semantic Scholar)
            date_to:          ISO date upper bound (YYYY-MM-DD)
            use_cache:        Whether to serve from cache (default True)

        Returns dict with keys:
            results, total, providers_used, providers_failed,
            providers_skipped, query, took_ms, cached
        """
        if providers is None:
            providers = DEFAULT_PROVIDERS

        # ── Cache lookup ──────────────────────────────────────────────────────
        cache_key = self._cache.make_key(
            query, providers, max_per_provider, page, date_from, date_to
        )
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                cached["cached"] = True
                return cached

        # ── Fan-out ───────────────────────────────────────────────────────────
        start = time.monotonic()
        all_results: List[SearchResult] = []
        providers_used: List[str] = []
        providers_failed: List[str] = []
        providers_skipped: List[str] = []

        active: Dict[str, BaseProvider] = {}
        for pid in providers:
            p = self._providers.get(pid)
            if p is None:
                providers_skipped.append(pid)
            elif not p.is_available():
                providers_skipped.append(pid)
            else:
                active[pid] = p

        with ThreadPoolExecutor(max_workers=min(len(active), 15)) as executor:
            future_map = {
                executor.submit(
                    _safe_search, p, query, max_per_provider, page,
                    date_from, date_to
                ): pid
                for pid, p in active.items()
            }

            for future in as_completed(future_map, timeout=timeout_secs):
                pid = future_map[future]
                try:
                    results, error = future.result()
                    if error:
                        logger.warning(f"Provider {pid}: {error}")
                        providers_failed.append(pid)
                    else:
                        all_results.extend(results)
                        providers_used.append(pid)
                except TimeoutError:
                    logger.warning(f"Provider {pid} timed out")
                    providers_failed.append(pid)
                except Exception as exc:
                    logger.warning(f"Provider {pid} unexpected error: {exc}")
                    providers_failed.append(pid)

        # ── Post-process ──────────────────────────────────────────────────────
        # Client-side date filtering (catches providers that don't support it natively)
        if date_from or date_to:
            all_results = _filter_by_date(all_results, date_from, date_to)

        deduped = _deduplicate(all_results)
        interleaved = _interleave(deduped)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        output = {
            "results": [r.to_dict() for r in interleaved],
            "total": len(interleaved),
            "providers_used": providers_used,
            "providers_failed": providers_failed,
            "providers_skipped": providers_skipped,
            "query": query,
            "took_ms": elapsed_ms,
            "cached": False,
            "date_from": date_from,
            "date_to": date_to,
        }

        # Store in cache
        if use_cache:
            self._cache.put(cache_key, output)

        return output

    # ── Provider info ─────────────────────────────────────────────────────────

    def get_providers_info(self) -> List[dict]:
        return [p.info() for p in self._providers.values()]

    def clear_cache(self) -> None:
        self._cache._cache.clear()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_search(
    provider: BaseProvider,
    query: str,
    max_results: int,
    page: int,
    date_from: Optional[str],
    date_to: Optional[str],
):
    """Call provider.search() with optional date kwargs; catch all exceptions."""
    try:
        import inspect
        sig = inspect.signature(provider.search)
        if "date_from" in sig.parameters:
            results = provider.search(
                query, max_results=max_results, page=page,
                date_from=date_from, date_to=date_to,
            )
        else:
            results = provider.search(query, max_results=max_results, page=page)
        return results, None
    except Exception as exc:
        return [], str(exc)


def _deduplicate(results: List[SearchResult]) -> List[SearchResult]:
    seen: set = set()
    out: List[SearchResult] = []
    for r in results:
        key = _norm_url(r.url)
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _norm_url(url: str) -> str:
    import re
    url = url.lower().rstrip("/")
    url = re.sub(r"^https?://www\.", "https://", url)
    url = re.sub(r"^https?://", "https://", url)
    return url


def _interleave(results: List[SearchResult]) -> List[SearchResult]:
    """Round-robin across providers so results from all sources appear early."""
    buckets: Dict[str, List[SearchResult]] = {}
    for r in results:
        buckets.setdefault(r.source_id, []).append(r)

    out: List[SearchResult] = []
    while any(buckets.values()):
        for key in list(buckets.keys()):
            if buckets[key]:
                out.append(buckets[key].pop(0))
    return out


def _filter_by_date(
    results: List[SearchResult],
    date_from: Optional[str],
    date_to: Optional[str],
) -> List[SearchResult]:
    """Filter results by published_at field where available."""
    from datetime import datetime, timezone

    def _parse(s: str) -> Optional[datetime]:
        if not s:
            return None
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(s[:19], fmt[:len(s)])
                return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d
            except ValueError:
                continue
        return None

    lo = _parse(date_from) if date_from else None
    hi = _parse(date_to) if date_to else None

    out = []
    for r in results:
        if not r.published_at:
            out.append(r)  # keep undated results
            continue
        d = _parse(r.published_at)
        if d is None:
            out.append(r)
            continue
        if lo and d < lo:
            continue
        if hi and d > hi:
            continue
        out.append(r)
    return out
