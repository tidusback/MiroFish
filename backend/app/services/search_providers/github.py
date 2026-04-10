"""
GitHub Provider
===============
Searches GitHub repositories, issues, commits, and code.
Surfaces leaked documents, internal tools, security research,
and whistleblower repositories that may be buried in search engines.

No API key required (public search: 10 req/min unauthenticated).
Optional: set GITHUB_TOKEN for higher rate limits (5,000 req/hour).
"""

import logging
from typing import List

from .base import BaseProvider, SearchResult, SourceType

logger = logging.getLogger("mirofish.search.github")


class GitHubProvider(BaseProvider):
    NAME = "GitHub"
    ID = "github"
    SOURCE_TYPE = SourceType.CODE
    REQUIRES_KEY = False

    _REPOS_URL = "https://api.github.com/search/repositories"
    _CODE_URL = "https://api.github.com/search/code"
    _ISSUES_URL = "https://api.github.com/search/issues"

    def __init__(self, token: str = ""):
        self._token = token

    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.error("requests not installed")
            return []

        results: List[SearchResult] = []
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MiroFishSearch/1.0",
        }
        if self._token:
            headers["Authorization"] = f"token {self._token}"

        per_source = max(2, max_results // 2)

        # Search repositories
        try:
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_source,
                "page": page,
            }
            resp = requests.get(self._REPOS_URL, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                for item in resp.json().get("items", []):
                    results.append(
                        SearchResult(
                            title=item.get("full_name", ""),
                            url=item.get("html_url", ""),
                            snippet=(item.get("description") or "")
                            + f"  ★{item.get('stargazers_count', 0)}  "
                            + (f"· {item.get('language', '')}" if item.get("language") else ""),
                            source=self.NAME,
                            source_id=self.ID,
                            source_type=self.SOURCE_TYPE,
                            published_at=item.get("updated_at"),
                            author=item.get("owner", {}).get("login", ""),
                            extra={
                                "stars": item.get("stargazers_count", 0),
                                "forks": item.get("forks_count", 0),
                                "language": item.get("language", ""),
                                "topics": item.get("topics", []),
                                "type": "repository",
                            },
                        )
                    )
        except Exception as exc:
            logger.warning(f"GitHub repo search failed: {exc}")

        # Search issues/PRs for discussions
        try:
            if len(results) < max_results:
                params = {
                    "q": query,
                    "sort": "updated",
                    "order": "desc",
                    "per_page": per_source,
                    "page": page,
                }
                resp = requests.get(self._ISSUES_URL, params=params, headers=headers, timeout=10)
                if resp.status_code == 200:
                    for item in resp.json().get("items", []):
                        results.append(
                            SearchResult(
                                title=item.get("title", ""),
                                url=item.get("html_url", ""),
                                snippet=(item.get("body") or "")[:300],
                                source=self.NAME,
                                source_id=self.ID,
                                source_type=self.SOURCE_TYPE,
                                published_at=item.get("created_at"),
                                author=item.get("user", {}).get("login", ""),
                                extra={
                                    "state": item.get("state", ""),
                                    "comments": item.get("comments", 0),
                                    "type": "issue" if "pull_request" not in item else "pull_request",
                                    "repo": item.get("repository_url", "").replace(
                                        "https://api.github.com/repos/", ""
                                    ),
                                },
                            )
                        )
        except Exception as exc:
            logger.warning(f"GitHub issue search failed: {exc}")

        return results[:max_results]
