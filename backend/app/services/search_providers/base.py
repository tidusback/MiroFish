"""
Base classes for search providers
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class SourceType(str, Enum):
    WEB = "web"
    SOCIAL = "social"
    ACADEMIC = "academic"
    ARCHIVE = "archive"
    DARKWEB = "darkweb"
    CODE = "code"
    ENCYCLOPEDIA = "encyclopedia"
    ALTERNATIVE = "alternative"


@dataclass
class SearchResult:
    """Unified search result from any provider."""
    title: str
    url: str
    snippet: str
    source: str            # Provider display name, e.g. "DuckDuckGo"
    source_id: str         # Provider internal ID, e.g. "duckduckgo"
    source_type: SourceType

    published_at: Optional[str] = None
    author: Optional[str] = None
    score: float = 1.0
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "snippet": self.snippet,
            "source": self.source,
            "source_id": self.source_id,
            "source_type": self.source_type.value,
            "published_at": self.published_at,
            "author": self.author,
            "score": self.score,
            "extra": self.extra,
        }


class BaseProvider(ABC):
    """Abstract base class for all search providers."""

    # Human-readable display name
    NAME: str = "Unknown"
    # Internal ID used in API calls
    ID: str = "unknown"
    # What kind of results this source returns
    SOURCE_TYPE: SourceType = SourceType.WEB
    # Whether an API key is required
    REQUIRES_KEY: bool = False

    # Shared session headers to avoid duplicate allocation
    _DEFAULT_HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) "
            "Gecko/20100101 Firefox/125.0"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
    }

    def is_available(self) -> bool:
        """Returns True if this provider can be used (keys present, etc.)."""
        return True

    @abstractmethod
    def search(self, query: str, max_results: int = 10, page: int = 1) -> List[SearchResult]:
        """Execute a search and return results."""
        ...

    def info(self) -> dict:
        return {
            "id": self.ID,
            "name": self.NAME,
            "source_type": self.SOURCE_TYPE.value,
            "requires_key": self.REQUIRES_KEY,
            "available": self.is_available(),
        }
