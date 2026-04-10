"""
Reddit Provider
===============
Searches Reddit via the public JSON API (no auth required).
Surfaces community discussions, whistleblower posts, and crowd-sourced
investigations that mainstream search rarely surfaces.

No API key required for public search.
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.reddit")


class RedditProvider(BaseProvider):
    NAME = "Reddit"
    ID = "reddit"
    SOURCE_TYPE = SourceType.SOCIAL
    REQUIRES_KEY = False

    _SEARCH_URL = "https://www.reddit.com/search.json"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            headers = {
                **self._DEFAULT_HEADERS,
                "User-Agent": "MiroFishSearch/1.0 (uncensored meta-search aggregator)",
            }
            params = {
                "q": query,
                "sort": "relevance",
                "limit": max_results,
                "type": "link,sr",
                "include_over_18": "on",  # Don't filter adult content subreddits
                "after": "",
            }
            if page > 1:
                # We can't page without `after` token, so approximate
                params["count"] = (page - 1) * max_results

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=15
            )
            resp.raise_for_status()
            data = resp.json()

            children = data.get("data", {}).get("children", [])
            for child in children:
                post = child.get("data", {})
                if not post:
                    continue

                url = post.get("url", "")
                permalink = "https://www.reddit.com" + post.get("permalink", "")

                # For self-posts the "url" is the reddit link itself
                if post.get("is_self"):
                    display_url = permalink
                else:
                    display_url = url

                title = post.get("title", "")
                snippet = _build_snippet(post)

                results.append(
                    SearchResult(
                        title=title,
                        url=display_url,
                        snippet=snippet,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=post.get("author"),
                        published_at=_ts(post.get("created_utc")),
                        extra={
                            "subreddit": post.get("subreddit_name_prefixed", ""),
                            "score": post.get("score", 0),
                            "num_comments": post.get("num_comments", 0),
                            "upvote_ratio": post.get("upvote_ratio", 0),
                            "flair": post.get("link_flair_text", ""),
                            "reddit_url": permalink,
                            "original_url": url if not post.get("is_self") else "",
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"Reddit search failed: {exc}")

        return results


def _build_snippet(post: dict) -> str:
    parts = []
    selftext = post.get("selftext", "")
    if selftext and selftext not in ("[removed]", "[deleted]"):
        parts.append(selftext[:300])
    sub = post.get("subreddit_name_prefixed", "")
    if sub:
        parts.append(f"in {sub}")
    score = post.get("score", 0)
    if score:
        parts.append(f"↑{score}")
    comments = post.get("num_comments", 0)
    if comments:
        parts.append(f"{comments} comments")
    return " · ".join(parts)


def _ts(unix_ts) -> str:
    if not unix_ts:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.fromtimestamp(float(unix_ts), tz=timezone.utc).isoformat()
    except Exception:
        return None
