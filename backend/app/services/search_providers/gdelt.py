"""
GDELT Provider
==============
Searches the GDELT Project — the world's largest open dataset of
global news media. GDELT monitors every major newspaper, broadcast,
and online publication across 100+ languages in real time.

Unlike Google News, it has no editorial filtering and surfaces
coverage from international, regional, and fringe media that US
search engines demote or ignore.

Free API, no key required.
Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

import logging
from typing import List, Optional
from urllib.parse import quote

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.gdelt")


class GDELTProvider(BaseProvider):
    NAME = "GDELT"
    ID = "gdelt"
    SOURCE_TYPE = SourceType.ALTERNATIVE
    REQUIRES_KEY = False

    _API_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    def search(
        self,
        query: str,
        max_results: int = 10,
        page: int = 1,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        try:
            params = {
                "query": query,
                "mode": "artlist",
                "maxrecords": min(max_results, 250),
                "format": "json",
                "sort": "DateDesc",
                # Tone: -100 (most negative) to +100 (most positive)
                # Omitting tone filter to show ALL coverage
            }

            # Date filters: YYYYMMDDHHMMSS
            if date_from:
                params["startdatetime"] = _to_gdelt_date(date_from, end=False)
            if date_to:
                params["enddatetime"] = _to_gdelt_date(date_to, end=True)

            headers = {**self._DEFAULT_HEADERS, "Accept": "application/json"}
            resp = requests.get(self._API_URL, params=params, headers=headers, timeout=15)
            resp.raise_for_status()

            data = resp.json()

            # Skip the first (page-1)*max_results results for pagination
            articles = data.get("articles", [])
            start = (page - 1) * max_results
            articles = articles[start : start + max_results]

            for art in articles:
                url = art.get("url", "")
                if not url:
                    continue

                title = art.get("title", "")
                seendate = art.get("seendate", "")
                domain = art.get("domain", "")
                language = art.get("language", "")
                sourcecountry = art.get("sourcecountry", "")
                tone = art.get("tone")

                # Format publication date
                pub_date = None
                if seendate and len(seendate) >= 8:
                    try:
                        from datetime import datetime, timezone
                        d = datetime.strptime(seendate[:14], "%Y%m%d%H%M%S")
                        pub_date = d.replace(tzinfo=timezone.utc).isoformat()
                    except Exception:
                        pub_date = seendate

                snippet_parts = []
                if domain:
                    snippet_parts.append(f"Source: {domain}")
                if sourcecountry:
                    snippet_parts.append(f"Country: {sourcecountry}")
                if language and language != "English":
                    snippet_parts.append(f"Language: {language}")
                if tone is not None:
                    sentiment = "positive" if float(tone) > 0 else "negative"
                    snippet_parts.append(f"Sentiment: {sentiment} ({tone:.1f})")

                results.append(
                    SearchResult(
                        title=title or url,
                        url=url,
                        snippet=" · ".join(snippet_parts),
                        source=self.NAME,
                        source_id=self.ID,
                        source_type=self.SOURCE_TYPE,
                        published_at=pub_date,
                        extra={
                            "domain": domain,
                            "language": language,
                            "country": sourcecountry,
                            "tone": tone,
                        },
                    )
                )

        except Exception as exc:
            logger.warning(f"GDELT search failed: {exc}")

        return results


def _to_gdelt_date(date_str: str, end: bool) -> str:
    """Convert ISO date string to GDELT YYYYMMDDHHMMSS format."""
    try:
        from datetime import datetime
        # Accept YYYY-MM-DD or full ISO
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                d = datetime.strptime(date_str[:19], fmt)
                if end:
                    return d.strftime("%Y%m%d235959")
                return d.strftime("%Y%m%d000000")
            except ValueError:
                continue
    except Exception:
        pass
    return date_str  # Return as-is if we can't parse it
