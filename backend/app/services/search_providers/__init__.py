"""
Uncensored Meta-Search Engine - Provider Registry
==================================================
Aggregates results from diverse, ad-free, unfiltered sources:

  Web:           DuckDuckGo, Brave Search, SearXNG
  Social:        Reddit, HackerNews
  Academic:      arXiv, Semantic Scholar
  Archive:       Internet Archive (Wayback Machine), CourtListener (US courts)
  Dark Web:      Ahmia.fi (Tor .onion index, clearnet)
  Alt/Indie:     Marginalia (independent index), GDELT (global news), Alt-News RSS
  Transparency:  OpenCorporates (200M+ company records)
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

__all__ = [
    'SearchResult', 'BaseProvider', 'SourceType',
    'DuckDuckGoProvider',
    'BraveSearchProvider',
    'HackerNewsProvider',
    'RedditProvider',
    'WikipediaProvider',
    'ArxivProvider',
    'SemanticScholarProvider',
    'ArchiveOrgProvider',
    'AhmiaProvider',
    'MarginaliaProvider',
    'GitHubProvider',
    'CourtListenerProvider',
    'GDELTProvider',
    'AlternativeNewsProvider',
    'OpenCorporatesProvider',
]

