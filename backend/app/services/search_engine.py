"""
MiroFish Uncensored Meta-Search Engine
=======================================
Aggregates results from 11 diverse sources in parallel:

  Web:           DuckDuckGo (no ads, scraping), Brave Search (independent index)
  Social:        Reddit, Hacker News
  Academic:      arXiv (preprints), Semantic Scholar (200M+ papers)
  Archive:       Internet Archive (deleted/censored content)
  Dark Web:      Ahmia.fi (Tor .onion index, clearnet accessible)
  Alternative:   Marginalia (non-commercial, anti-SEO index)
  Encyclopedia:  Wikipedia
  Code:          GitHub

Philosophy:
  - Zero ads
  - Zero tracking
  - Zero filter bubble
  - Zero censorship (except CSAM which Ahmia removes itself)
  - Surfaces results Google buries: academic pre-prints, dark web,
    archived deleted pages, community discussions, leaked code, etc.
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from typing import Dict, List, Optional

from .search_providers import (
    AhmiaProvider,
    ArxivProvider,
    ArchiveOrgProvider,
    BaseProvider,
    BraveSearchProvider,
    DuckDuckGoProvider,
    GitHubProvider,
    HackerNewsProvider,
    MarginaliaProvider,
    RedditProvider,
    SearchResult,
    SemanticScholarProvider,
    WikipediaProvider,
)

logger = logging.getLogger("mirofish.search_engine")

# Canonical provider registry
_PROVIDER_REGISTRY: Dict[str, type] = {
    "duckduckgo": DuckDuckGoProvider,
    "brave": BraveSearchProvider,
    "hackernews": HackerNewsProvider,
    "reddit": RedditProvider,
    "wikipedia": WikipediaProvider,
    "arxiv": ArxivProvider,
    "semantic_scholar": SemanticScholarProvider,
    "archive_org": ArchiveOrgProvider,
    "ahmia": AhmiaProvider,
    "marginalia": MarginaliaProvider,
    "github": GitHubProvider,
}

# Default provider set (excludes providers needing API keys by default)
DEFAULT_PROVIDERS = [
    "duckduckgo",
    "hackernews",
    "reddit",
    "wikipedia",
    "arxiv",
    "archive_org",
    "marginalia",
]

# Full uncensored set including dark web index
DEEP_PROVIDERS = DEFAULT_PROVIDERS + ["ahmia", "semantic_scholar", "github"]


class SearchEngine:
    """
    Parallel meta-search aggregator.

    Usage:
        engine = SearchEngine.from_config(app_config)
        result = engine.search("your query", providers=DEEP_PROVIDERS, max_per_provider=10)
    """

    def __init__(self, providers: Dict[str, BaseProvider]):
        self._providers = providers

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def from_config(cls, config) -> "SearchEngine":
        """Build the engine from Flask app config (reads API keys from env)."""
        providers: Dict[str, BaseProvider] = {}

        brave_key = getattr(config, "BRAVE_SEARCH_API_KEY", "") or ""
        ss_key = getattr(config, "SEMANTIC_SCHOLAR_API_KEY", "") or ""
        github_token = getattr(config, "GITHUB_TOKEN", "") or ""
        marginalia_key = getattr(config, "MARGINALIA_API_KEY", "") or ""

        for pid, cls_ref in _PROVIDER_REGISTRY.items():
            try:
                if pid == "brave":
                    instance = BraveSearchProvider(api_key=brave_key)
                elif pid == "semantic_scholar":
                    instance = SemanticScholarProvider(api_key=ss_key)
                elif pid == "github":
                    instance = GitHubProvider(token=github_token)
                elif pid == "marginalia":
                    instance = MarginaliaProvider(api_key=marginalia_key)
                else:
                    instance = cls_ref()
                providers[pid] = instance
            except Exception as exc:
                logger.warning(f"Failed to init provider {pid}: {exc}")

        return cls(providers)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        providers: Optional[List[str]] = None,
        max_per_provider: int = 10,
        page: int = 1,
        timeout_secs: float = 25.0,
    ) -> dict:
        """
        Run parallel search across all requested providers.

        Returns:
            {
                "results": [SearchResult.to_dict(), ...],
                "total": int,
                "providers_used": [...],
                "providers_failed": [...],
                "providers_skipped": [...],   # unavailable (missing API key)
                "query": str,
                "took_ms": int,
            }
        """
        if providers is None:
            providers = DEFAULT_PROVIDERS

        start = time.monotonic()
        all_results: List[SearchResult] = []
        providers_used: List[str] = []
        providers_failed: List[str] = []
        providers_skipped: List[str] = []

        # Determine which providers are available
        active: Dict[str, BaseProvider] = {}
        for pid in providers:
            p = self._providers.get(pid)
            if p is None:
                logger.debug(f"Unknown provider: {pid}")
                providers_skipped.append(pid)
            elif not p.is_available():
                providers_skipped.append(pid)
            else:
                active[pid] = p

        # Fan out in parallel
        with ThreadPoolExecutor(max_workers=min(len(active), 12)) as executor:
            future_map = {
                executor.submit(_safe_search, p, query, max_per_provider, page): pid
                for pid, p in active.items()
            }

            for future in as_completed(future_map, timeout=timeout_secs):
                pid = future_map[future]
                try:
                    results, error = future.result()
                    if error:
                        logger.warning(f"Provider {pid} error: {error}")
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

        # Deduplicate by normalised URL
        deduped = _deduplicate(all_results)

        # Sort: by source_type diversity first, then by position
        deduped = _interleave(deduped)

        elapsed_ms = int((time.monotonic() - start) * 1000)

        return {
            "results": [r.to_dict() for r in deduped],
            "total": len(deduped),
            "providers_used": providers_used,
            "providers_failed": providers_failed,
            "providers_skipped": providers_skipped,
            "query": query,
            "took_ms": elapsed_ms,
        }

    # ------------------------------------------------------------------
    # Providers info
    # ------------------------------------------------------------------

    def get_providers_info(self) -> List[dict]:
        """Return metadata for all registered providers."""
        return [p.info() for p in self._providers.values()]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _safe_search(provider: BaseProvider, query: str, max_results: int, page: int):
    """Run provider.search() and catch all exceptions."""
    try:
        results = provider.search(query, max_results=max_results, page=page)
        return results, None
    except Exception as exc:
        return [], str(exc)


def _deduplicate(results: List[SearchResult]) -> List[SearchResult]:
    """Remove duplicate results by normalised URL."""
    seen: set = set()
    out: List[SearchResult] = []
    for r in results:
        key = _norm_url(r.url)
        if key and key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _norm_url(url: str) -> str:
    """Normalise URL for deduplication."""
    import re
    url = url.lower().rstrip("/")
    url = re.sub(r"^https?://www\.", "https://", url)
    url = re.sub(r"^https?://", "https://", url)
    return url


def _interleave(results: List[SearchResult]) -> List[SearchResult]:
    """
    Interleave results from different source types so the user sees
    diverse perspectives rather than all results from one provider first.
    """
    buckets: Dict[str, List[SearchResult]] = {}
    for r in results:
        key = r.source_id
        buckets.setdefault(key, []).append(r)

    out: List[SearchResult] = []
    while any(buckets.values()):
        for key in list(buckets.keys()):
            if buckets[key]:
                out.append(buckets[key].pop(0))
    return out
