"""
Alternative News RSS Provider
==============================
Aggregates RSS feeds from independent, investigative, and alternative
news outlets that Google systematically demotes in search rankings.

Sources span the full political spectrum of dissent — from left-wing
investigative journalism (The Intercept, ProPublica) to libertarian
(Reason), anti-war (Consortium News, AntiWar.com), open-source
intelligence (Bellingcat), and international perspectives (Al Monitor,
FAIR, WSWS).

These outlets are the ones that broke stories on:
  - NSA mass surveillance (The Intercept / Snowden)
  - CIA torture programmes (ProPublica)
  - Iraq War deceptions (Consortium News)
  - Corporate regulatory capture (various)

No API key required. Uses feedparser.
Results are scored by keyword relevance to the query.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.alt_news")

# ── Feed registry ──────────────────────────────────────────────────────────

ALT_NEWS_FEEDS: Dict[str, Tuple[str, str]] = {
    # (feed_url, display_name)
    "theintercept":   ("https://theintercept.com/feed/?rss", "The Intercept"),
    "propublica":     ("https://feeds.propublica.org/propublica/main", "ProPublica"),
    "thegrayzone":    ("https://thegrayzone.com/feed/", "The Grayzone"),
    "consortiumnews": ("https://consortiumnews.com/feed/", "Consortium News"),
    "bellingcat":     ("https://www.bellingcat.com/feed/", "Bellingcat"),
    "commondreams":   ("https://www.commondreams.org/rss.xml", "Common Dreams"),
    "truthout":       ("https://truthout.org/feed/", "Truthout"),
    "democracynow":   ("https://www.democracynow.org/democracynow.rss", "Democracy Now"),
    "jacobin":        ("https://jacobin.com/feed/", "Jacobin"),
    "counterpunch":   ("https://www.counterpunch.org/feed/", "CounterPunch"),
    "scheerpost":     ("https://scheerpost.com/feed/", "ScheerPost"),
    "antiwar":        ("https://feeds.feedburner.com/antiwarcom-main", "AntiWar.com"),
    "mintpress":      ("https://www.mintpressnews.com/feed/", "MintPress News"),
    "reason":         ("https://reason.com/feed/", "Reason"),
    "fair":           ("https://fair.org/feed/", "FAIR (Media Criticism)"),
    "wsws":           ("https://www.wsws.org/rss.xml", "World Socialist Web Site"),
    "zerohedge":      ("https://feeds.feedburner.com/zerohedge/feed", "ZeroHedge"),
    "off_guardian":   ("https://off-guardian.org/feed/", "Off-Guardian"),
    "realclearinv":   ("https://www.realclearinvestigations.com/feed/", "RCI"),
    "techdirt":       ("https://www.techdirt.com/techdirt_rss.xml", "Techdirt"),
}

# Feed content cache: {feed_id: (fetched_at_unix, [articles])}
_FEED_CACHE: Dict[str, Tuple[float, list]] = {}
_CACHE_TTL = 900  # 15 minutes


class AlternativeNewsProvider(BaseProvider):
    NAME = "Alt-News RSS"
    ID = "alt_news"
    SOURCE_TYPE = SourceType.ALTERNATIVE
    REQUIRES_KEY = False

    # Max articles to keep per feed (memory cap)
    _MAX_PER_FEED = 50

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed")
            return []

        # Fetch all feeds (with caching)
        all_articles = self._get_all_articles(feedparser)

        # Score by keyword relevance
        keywords = [w.lower() for w in re.split(r"\W+", query) if len(w) > 2]
        if not keywords:
            keywords = [query.lower()]

        scored: List[Tuple[float, SearchResult]] = []
        for art in all_articles:
            score = _score_article(art, keywords)
            if score > 0:
                scored.append((score, art))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)

        start = (page - 1) * max_results
        top = scored[start : start + max_results]
        return [r for _, r in top]

    def _get_all_articles(self, feedparser_mod) -> List[SearchResult]:
        """Fetch all feeds concurrently, returning cached results where fresh."""
        now = time.time()
        stale_feeds = [
            fid for fid, (ts, _) in _FEED_CACHE.items()
            if now - ts > _CACHE_TTL
        ]
        missing_feeds = [
            fid for fid in ALT_NEWS_FEEDS
            if fid not in _FEED_CACHE
        ]
        feeds_to_refresh = list(set(stale_feeds + missing_feeds))

        if feeds_to_refresh:
            with ThreadPoolExecutor(max_workers=min(len(feeds_to_refresh), 10)) as ex:
                futures = {
                    ex.submit(
                        _fetch_feed, fid, ALT_NEWS_FEEDS[fid][0],
                        ALT_NEWS_FEEDS[fid][1], feedparser_mod, self._MAX_PER_FEED
                    ): fid
                    for fid in feeds_to_refresh
                }
                for future in as_completed(futures, timeout=20):
                    fid = futures[future]
                    try:
                        articles = future.result()
                        _FEED_CACHE[fid] = (time.time(), articles)
                    except Exception as exc:
                        logger.debug(f"Feed {fid} fetch failed: {exc}")
                        if fid not in _FEED_CACHE:
                            _FEED_CACHE[fid] = (time.time(), [])

        all_articles: List[SearchResult] = []
        for fid, (_, articles) in _FEED_CACHE.items():
            all_articles.extend(articles)
        return all_articles


def _fetch_feed(
    feed_id: str,
    feed_url: str,
    source_name: str,
    feedparser_mod,
    max_per_feed: int,
) -> List[SearchResult]:
    """Fetch a single RSS feed and return SearchResult list."""
    try:
        feed = feedparser_mod.parse(feed_url)
        results = []
        for entry in feed.entries[:max_per_feed]:
            url = entry.get("link", "")
            title = entry.get("title", "")
            if not url or not title:
                continue

            # Extract snippet from summary or content
            raw = (
                entry.get("content", [{}])[0].get("value", "")
                or entry.get("summary", "")
                or entry.get("description", "")
            )
            snippet = re.sub(r"<[^>]+>", " ", raw)
            snippet = re.sub(r"\s+", " ", snippet).strip()[:500]

            # Publication date
            pub_date = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub_date = datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).isoformat()
                except Exception:
                    pass

            author = entry.get("author") or entry.get("dc_creator") or None

            results.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=snippet,
                    source=source_name,
                    source_id="alt_news",
                    source_type=SourceType.ALTERNATIVE,
                    published_at=pub_date,
                    author=author,
                    extra={"feed_id": feed_id},
                )
            )
        return results
    except Exception as exc:
        logger.debug(f"Failed fetching {source_name}: {exc}")
        return []


def _score_article(art: SearchResult, keywords: List[str]) -> float:
    """Score an article by keyword matches in title, snippet."""
    text = f"{art.title} {art.snippet}".lower()
    score = 0.0
    for kw in keywords:
        if kw in art.title.lower():
            score += 2.0   # Title match is worth more
        elif kw in text:
            score += 1.0
    return score
