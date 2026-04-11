"""
Uncensored Meta-Search Engine - Provider Registry
==================================================
19 diverse sources aggregated in parallel:

  Web:           DuckDuckGo, Brave Search
  Social:        Reddit, HackerNews, Mastodon (Fediverse)
  Academic:      arXiv, Semantic Scholar, PubMed (35M+ biomedical papers)
  Archive:       Internet Archive, CourtListener (US courts), DocumentCloud (FOIA)
  Dark Web:      Ahmia.fi (Tor index, clearnet), Tor Search (direct, if Tor running)
  Alt/Indie:     Marginalia, GDELT (global news), Alt-News RSS, OpenCorporates
  Encyclopedia:  Wikipedia
  Code:          GitHub
"""

from .base import SearchResult, BaseProvider, SourceType
from .duckduckgo import DuckDuckGoProvider
from .brave import BraveSearchProvider
from .hackernews import HackerNewsProvider
from .reddit import RedditProvider
from .wikipedia import WikipediaProvider
from .arxiv import ArxivProvider
from .semantic_scholar import SemanticScholarProvider
from .archive_org import ArchiveOrgProvider
from .ahmia import AhmiaProvider
from .marginalia import MarginaliaProvider
from .github import GitHubProvider
from .courtlistener import CourtListenerProvider
from .gdelt import GDELTProvider
from .alternative_news import AlternativeNewsProvider
from .opencorporates import OpenCorporatesProvider
from .documentcloud import DocumentCloudProvider
from .pubmed import PubMedProvider
from .mastodon import MastodonProvider
from .tor_search import TorSearchProvider

__all__ = [
    'SearchResult', 'BaseProvider', 'SourceType',
    'DuckDuckGoProvider', 'BraveSearchProvider',
    'HackerNewsProvider', 'RedditProvider', 'MastodonProvider',
    'WikipediaProvider',
    'ArxivProvider', 'SemanticScholarProvider', 'PubMedProvider',
    'ArchiveOrgProvider', 'CourtListenerProvider', 'DocumentCloudProvider',
    'AhmiaProvider', 'TorSearchProvider',
    'MarginaliaProvider', 'GDELTProvider', 'AlternativeNewsProvider', 'OpenCorporatesProvider',
    'GitHubProvider',
]
