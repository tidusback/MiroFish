"""
Mastodon / Fediverse Provider
==============================
Searches the Mastodon federated social network — the decentralised,
open-source alternative to Twitter/X.

Mastodon has no algorithmic censorship, no corporate content moderation,
and no advertiser pressure. Posts are not deranked or shadow-banned for
political content. Whistleblowers, journalists, and activists use it
specifically because it lacks centralised censorship.

Searches mastodon.social (the flagship instance) via its public API.
Returns posts with full text, author, and engagement metrics.

No API key required for public search.
Docs: https://docs.joinmastodon.org/methods/search/
"""

import logging
import re
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.mastodon")


class MastodonProvider(BaseProvider):
    NAME = "Mastodon"
    ID = "mastodon"
    SOURCE_TYPE = SourceType.SOCIAL
    REQUIRES_KEY = False

    # Use mastodon.social — the largest public instance
    _SEARCH_URL = "https://mastodon.social/api/v2/search"

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            offset = (page - 1) * max_results
            params = {
                "q": query,
                "type": "statuses",
                "limit": min(max_results, 40),
                "offset": offset,
                "resolve": "false",
            }
            headers = {
                **self._DEFAULT_HEADERS,
                "Accept": "application/json",
            }

            resp = requests.get(
                self._SEARCH_URL, params=params, headers=headers, timeout=12
            )
            resp.raise_for_status()
            data = resp.json()

            for status in data.get("statuses", []):
                # Strip HTML from content
                raw_content = status.get("content", "")
                text = re.sub(r"<[^>]+>", " ", raw_content)
                text = re.sub(r"\s+", " ", text).strip()

                if not text:
                    continue

                status_url = status.get("url", "") or status.get("uri", "")
                account = status.get("account", {}) or {}
                author = account.get("display_name") or account.get("username") or ""
                acct = account.get("acct", "")
                if acct and author:
                    author = f"{author} (@{acct})"

                created_at = status.get("created_at")
                reblogs = status.get("reblogs_count", 0)
                favourites = status.get("favourites_count", 0)
                replies = status.get("replies_count", 0)

                # Extract any attached link cards
                card = status.get("card") or {}
                card_url = card.get("url", "")
                card_title = card.get("title", "")

                title = card_title or text[:100]
                url = card_url or status_url

                snippet = text[:400]
                if card_url and card_title:
                    snippet = f"{text[:250]}\n→ {card_title}"

                results.append(
                    SearchResult(
                        title=title,
                        url=url,
                        snippet=snippet,
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        author=author,
                        published_at=created_at,
                        extra={
                            "reblogs": reblogs,
                            "favourites": favourites,
                            "replies": replies,
                            "mastodon_url": status_url,
                            "instance": "mastodon.social",
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"Mastodon search failed: {exc}")

        return results
