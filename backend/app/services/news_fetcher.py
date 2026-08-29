"""
News & Reliable Source Fetcher
==============================
Fetches content from:
  1. RSS / Atom feeds  (feedparser)
  2. Direct article URLs  (requests + BeautifulSoup)
  3. Inline "insider" / expert text provided by the user

Every article is tagged with its source name, credibility tier, and
publication date so the LLM sees *where* each piece of information comes
from when it builds the knowledge graph.

Credibility tiers
-----------------
  TIER_1  – Internationally recognised wire-services & newspapers (Reuters,
             AP, BBC, FT, NYT, WSJ, Bloomberg, The Economist, Le Monde, …)
  TIER_2  – Major national news outlets with established editorial standards
  TIER_3  – Blogs, niche publications, forums
  INSIDER – Manually supplied expert / insider text (user-labelled)
"""

import re
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger('mirofish.news_fetcher')

# ---------------------------------------------------------------------------
# Credibility tiers
# ---------------------------------------------------------------------------

TIER_1 = "TIER_1_AUTHORITATIVE"
TIER_2 = "TIER_2_ESTABLISHED"
TIER_3 = "TIER_3_GENERAL"
TIER_INSIDER = "INSIDER_EXPERT"

# Domain → (display_name, tier)
_TRUSTED_DOMAINS: dict = {
    # Wire services
    "reuters.com": ("Reuters", TIER_1),
    "apnews.com": ("Associated Press", TIER_1),
    "bloomberg.com": ("Bloomberg", TIER_1),
    "afp.com": ("AFP", TIER_1),
    # Major English-language press
    "bbc.com": ("BBC News", TIER_1),
    "bbc.co.uk": ("BBC News", TIER_1),
    "ft.com": ("Financial Times", TIER_1),
    "nytimes.com": ("New York Times", TIER_1),
    "wsj.com": ("Wall Street Journal", TIER_1),
    "economist.com": ("The Economist", TIER_1),
    "theguardian.com": ("The Guardian", TIER_1),
    "washingtonpost.com": ("Washington Post", TIER_1),
    "foreignaffairs.com": ("Foreign Affairs", TIER_1),
    "foreignpolicy.com": ("Foreign Policy", TIER_1),
    # International press
    "lemonde.fr": ("Le Monde", TIER_1),
    "spiegel.de": ("Der Spiegel", TIER_1),
    "elpais.com": ("El País", TIER_1),
    # Tier-2: established national outlets
    "cnn.com": ("CNN", TIER_2),
    "aljazeera.com": ("Al Jazeera", TIER_2),
    "dw.com": ("Deutsche Welle", TIER_2),
    "rfi.fr": ("RFI", TIER_2),
    "scmp.com": ("South China Morning Post", TIER_2),
    "japantimes.co.jp": ("Japan Times", TIER_2),
    "thehindu.com": ("The Hindu", TIER_2),
    "smh.com.au": ("Sydney Morning Herald", TIER_2),
    "politico.com": ("Politico", TIER_2),
    "axios.com": ("Axios", TIER_2),
    "theatlantic.com": ("The Atlantic", TIER_2),
    "vox.com": ("Vox", TIER_2),
    "nature.com": ("Nature", TIER_2),
    "science.org": ("Science", TIER_2),
}


def _get_source_info(url: str):
    """Return (source_name, credibility_tier) for a given URL."""
    try:
        host = urlparse(url).hostname or ""
        # strip www.
        host = re.sub(r"^www\.", "", host)
        for domain, info in _TRUSTED_DOMAINS.items():
            if host == domain or host.endswith("." + domain):
                return info
    except Exception:
        pass
    return ("Unknown Source", TIER_3)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SourceArticle:
    """A single piece of content from any external source."""
    url: str
    title: str
    content: str
    source_name: str
    credibility_tier: str
    published_at: Optional[str] = None   # ISO-8601 string
    author: Optional[str] = None
    error: Optional[str] = None          # set if fetch failed

    def to_annotated_text(self) -> str:
        """
        Return the article formatted with provenance metadata so the LLM
        can reason about source reliability when building the graph.
        """
        header_parts = [
            f"SOURCE: {self.source_name}",
            f"CREDIBILITY: {self.credibility_tier}",
        ]
        if self.published_at:
            header_parts.append(f"DATE: {self.published_at}")
        if self.author:
            header_parts.append(f"AUTHOR: {self.author}")
        if self.url:
            header_parts.append(f"URL: {self.url}")

        header = " | ".join(header_parts)
        title_line = f"TITLE: {self.title}" if self.title else ""

        parts = [f"[{header}]"]
        if title_line:
            parts.append(title_line)
        parts.append(self.content)
        return "\n".join(parts)

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "source_name": self.source_name,
            "credibility_tier": self.credibility_tier,
            "published_at": self.published_at,
            "author": self.author,
            "content_length": len(self.content),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Fetcher
# ---------------------------------------------------------------------------

class NewsFetcher:
    """Fetch text from RSS feeds and article URLs."""

    # Max characters to extract per article (avoids bloating the graph)
    MAX_ARTICLE_CHARS = 8000
    # Polite crawl delay between requests (seconds)
    CRAWL_DELAY = 0.5

    # --------------- RSS / Atom -----------------------------------------

    @classmethod
    def fetch_rss(cls, feed_url: str) -> List[SourceArticle]:
        """Parse an RSS/Atom feed and return its articles."""
        try:
            import feedparser
        except ImportError:
            logger.error("feedparser not installed. Run: pip install feedparser")
            return []

        logger.info(f"Fetching RSS feed: {feed_url}")
        feed = feedparser.parse(feed_url)

        articles: List[SourceArticle] = []
        feed_title = feed.feed.get("title", "")

        for entry in feed.entries:
            url = entry.get("link", "")
            source_name, tier = _get_source_info(url or feed_url)
            if feed_title and source_name == "Unknown Source":
                source_name = feed_title

            # Try to get full text, fall back to summary
            content = (
                entry.get("content", [{}])[0].get("value", "")
                or entry.get("summary", "")
                or entry.get("description", "")
            )
            content = _strip_html(content)[: cls.MAX_ARTICLE_CHARS]

            pub = entry.get("published", "") or entry.get("updated", "")
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                try:
                    pub = datetime(
                        *entry.published_parsed[:6], tzinfo=timezone.utc
                    ).isoformat()
                except Exception:
                    pass

            articles.append(
                SourceArticle(
                    url=url,
                    title=entry.get("title", ""),
                    content=content,
                    source_name=source_name,
                    credibility_tier=tier,
                    published_at=pub or None,
                    author=entry.get("author", None),
                )
            )

        logger.info(f"RSS feed yielded {len(articles)} articles from {feed_url}")
        return articles

    # --------------- Direct URL scraping --------------------------------

    @classmethod
    def fetch_url(cls, url: str) -> SourceArticle:
        """Fetch and extract text from a single article URL."""
        try:
            import requests
            from bs4 import BeautifulSoup
        except ImportError:
            return SourceArticle(
                url=url, title="", content="", source_name="Unknown",
                credibility_tier=TIER_3,
                error="requests/beautifulsoup4 not installed",
            )

        source_name, tier = _get_source_info(url)
        logger.info(f"Fetching URL ({tier}): {url}")

        try:
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (compatible; MiroFishBot/1.0; "
                    "+https://github.com/666ghj/MiroFish)"
                )
            }
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "lxml")

            # Title
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)
            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                title = og_title["content"]

            # Publication date
            pub_date = None
            for meta_name in (
                "article:published_time",
                "datePublished",
                "DC.date",
                "pubdate",
            ):
                tag = soup.find("meta", property=meta_name) or soup.find(
                    "meta", attrs={"name": meta_name}
                )
                if tag and tag.get("content"):
                    pub_date = tag["content"]
                    break

            # Author
            author = None
            author_tag = soup.find("meta", attrs={"name": "author"}) or soup.find(
                "meta", property="article:author"
            )
            if author_tag and author_tag.get("content"):
                author = author_tag["content"]

            # Main text: prefer <article>, then <main>, fall back to <body>
            body = (
                soup.find("article")
                or soup.find("main")
                or soup.find("div", class_=re.compile(r"article|content|story|post", re.I))
                or soup.body
            )
            content = ""
            if body:
                # Remove nav/footer/script/style noise
                for tag in body.find_all(
                    ["nav", "footer", "script", "style", "aside", "figure"]
                ):
                    tag.decompose()
                content = body.get_text(separator="\n", strip=True)
                # Collapse excessive blank lines
                content = re.sub(r"\n{3,}", "\n\n", content)
                content = content[: cls.MAX_ARTICLE_CHARS]

            time.sleep(cls.CRAWL_DELAY)
            return SourceArticle(
                url=url,
                title=title,
                content=content,
                source_name=source_name,
                credibility_tier=tier,
                published_at=pub_date,
                author=author,
            )

        except Exception as exc:
            logger.warning(f"Failed to fetch {url}: {exc}")
            return SourceArticle(
                url=url, title="", content="", source_name=source_name,
                credibility_tier=tier, error=str(exc),
            )

    # --------------- Insider / expert source ----------------------------

    @staticmethod
    def make_insider_article(
        content: str,
        label: str = "Anonymous Insider",
        tier: str = TIER_INSIDER,
    ) -> SourceArticle:
        """
        Wrap manually supplied insider text as a SourceArticle so it
        receives the same provenance annotation as fetched articles.
        """
        return SourceArticle(
            url="",
            title=f"Expert/Insider Source: {label}",
            content=content.strip(),
            source_name=label,
            credibility_tier=tier,
            published_at=datetime.now(timezone.utc).isoformat(),
        )

    # --------------- Batch helpers --------------------------------------

    @classmethod
    def fetch_all(
        cls,
        urls: List[str],
        rss_feeds: List[str],
        insider_entries: Optional[List[dict]] = None,
    ) -> List[SourceArticle]:
        """
        Fetch from multiple sources.

        Args:
            urls: Direct article URLs to scrape.
            rss_feeds: RSS/Atom feed URLs to parse.
            insider_entries: List of dicts with keys ``content`` and
                optionally ``label``.

        Returns:
            Combined list of SourceArticle objects (failed fetches omitted
            from the result unless they had at least a title).
        """
        articles: List[SourceArticle] = []

        # RSS feeds
        for feed_url in rss_feeds:
            try:
                articles.extend(cls.fetch_rss(feed_url))
            except Exception as exc:
                logger.warning(f"RSS fetch error for {feed_url}: {exc}")

        # Direct URLs
        for url in urls:
            art = cls.fetch_url(url)
            if art.content or art.title:
                articles.append(art)

        # Insider sources
        for entry in (insider_entries or []):
            text = (entry.get("content") or "").strip()
            if text:
                articles.append(
                    cls.make_insider_article(
                        content=text,
                        label=entry.get("label", "Anonymous Insider"),
                    )
                )

        return articles

    @staticmethod
    def articles_to_annotated_text(articles: List[SourceArticle]) -> str:
        """
        Combine all articles into a single annotated text block, ordered by
        credibility tier (TIER_1 first) so the LLM sees the most reliable
        information first.
        """
        tier_order = {TIER_1: 0, TIER_2: 1, TIER_3: 2, TIER_INSIDER: 3}
        sorted_articles = sorted(
            articles,
            key=lambda a: tier_order.get(a.credibility_tier, 99),
        )
        blocks = []
        for art in sorted_articles:
            if art.content or art.title:
                blocks.append(art.to_annotated_text())
        return "\n\n" + ("\n\n" + "=" * 60 + "\n\n").join(blocks)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_html(html: str) -> str:
    """Remove HTML tags from a string."""
    try:
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "lxml").get_text(separator=" ", strip=True)
    except Exception:
        return re.sub(r"<[^>]+>", " ", html)
