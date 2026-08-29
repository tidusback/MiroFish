import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import Mock

from flask import Blueprint


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _package(name, path):
    module = ModuleType(name)
    module.__path__ = [str(path)]
    sys.modules[name] = module
    return module


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_package("app", BACKEND_ROOT / "app")
api_package = _package("app.api", BACKEND_ROOT / "app" / "api")
_package("app.services", BACKEND_ROOT / "app" / "services")
_package("app.utils", BACKEND_ROOT / "app" / "utils")
api_package.search_bp = Blueprint("search", __name__)

_load("app.config", BACKEND_ROOT / "app" / "config.py")
_load("app.utils.logger", BACKEND_ROOT / "app" / "utils" / "logger.py")
search_service = _load(
    "app.services.search_service",
    BACKEND_ROOT / "app" / "services" / "search_service.py",
)
news_fetcher = _load(
    "app.services.news_fetcher",
    BACKEND_ROOT / "app" / "services" / "news_fetcher.py",
)
SourceArticle = news_fetcher.SourceArticle


def test_source_article_dict_includes_extracted_content():
    article = SourceArticle(
        url="https://example.com/article",
        title="Example",
        content="Extracted article text",
        source_name="Example",
        credibility_tier="TIER_3_GENERAL",
    )

    assert article.to_dict()["content"] == "Extracted article text"


def test_transport_failure_is_raised_to_the_aggregator(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = RuntimeError("rate limited")
    session = Mock()
    session.get.return_value = response
    monkeypatch.setattr(search_service, "_get_session", lambda: session)

    result = search_service.SearchAggregator().search(
        "query", engines=["reddit"], max_per_engine=1
    )

    assert result["engines_used"] == []
    assert result["engines_failed"][0]["engine"] == "reddit"
    assert "rate limited" in result["engines_failed"][0]["error"]


def test_unknown_engine_does_not_create_an_empty_executor():
    result = search_service.SearchAggregator().search(
        "query", engines=["google"], max_per_engine=1
    )

    assert result["results"] == []
    assert result["engines_used"] == []
    assert result["engines_failed"] == [
        {"engine": "google", "error": "Unknown or unavailable search engine"}
    ]


def test_search_api_imports_news_fetcher_from_defining_module():
    search = _load("app.api.search", BACKEND_ROOT / "app" / "api" / "search.py")

    assert search.NewsFetcher.__module__ == "app.services.news_fetcher"
