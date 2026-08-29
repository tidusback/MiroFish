"""
Search API Routes
=================
Exposes the uncensored multi-engine search aggregator over HTTP.

Endpoints
---------
  POST /api/search/query        - Search across selected engines
  POST /api/search/deep         - Deep search (all engines)
  GET  /api/search/engines      - List available engines + status
  POST /api/search/fetch        - Fetch & extract full article text
"""

import traceback
from flask import request, jsonify

from . import search_bp
from ..config import Config
from ..utils.logger import get_logger
from ..services.search_service import SearchAggregator
from ..services.news_fetcher import NewsFetcher

logger = get_logger("mirofish.api.search")


def _get_aggregator() -> SearchAggregator:
    return SearchAggregator(
        brave_api_key=getattr(Config, "BRAVE_API_KEY", "") or "",
        searxng_url=getattr(Config, "SEARXNG_URL", "") or "",
    )


# ---------------------------------------------------------------------------
# /api/search/engines  – list available engines
# ---------------------------------------------------------------------------

@search_bp.route("/engines", methods=["GET"])
def list_engines():
    """
    Return metadata for every search engine the service can use.

    Response:
        {
            "success": true,
            "engines": [
                {
                    "id": "duckduckgo",
                    "name": "DuckDuckGo",
                    "description": "...",
                    "requires_key": false,
                    "category": "general"
                },
                ...
            ]
        }
    """
    try:
        agg = _get_aggregator()
        return jsonify({"success": True, "engines": agg.available_engines()})
    except Exception as exc:
        logger.error(f"list_engines error: {exc}")
        return jsonify({"success": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# /api/search/query  – search selected engines
# ---------------------------------------------------------------------------

@search_bp.route("/query", methods=["POST"])
def query():
    """
    Search across one or more engines.

    Request JSON:
        {
            "query":           "...",            // required
            "engines":         ["duckduckgo", "reddit", ...],  // optional, all if omitted
            "max_per_engine":  8                 // optional, default 8
        }

    Response:
        {
            "success": true,
            "data": {
                "query": "...",
                "results": [ { title, url, snippet, source_engine, source_label, published, extra }, ... ],
                "total": 42,
                "engines_used": ["duckduckgo", "reddit"],
                "engines_failed": []
            }
        }
    """
    try:
        body = request.get_json() or {}
        q = (body.get("query") or "").strip()
        if not q:
            return jsonify({"success": False, "error": "Query parameter 'query' is required"}), 400

        engines = body.get("engines") or None
        max_per = int(body.get("max_per_engine", 8))
        max_per = max(1, min(max_per, 20))

        logger.info(f"Search query: {q!r}  engines={engines}  max_per={max_per}")
        agg = _get_aggregator()
        result = agg.search(q, engines=engines, max_per_engine=max_per)

        return jsonify({"success": True, "data": result})

    except Exception as exc:
        logger.error(f"query error: {exc}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


# ---------------------------------------------------------------------------
# /api/search/deep  – full deep search (all engines)
# ---------------------------------------------------------------------------

@search_bp.route("/deep", methods=["POST"])
def deep_query():
    """
    Deep search: runs every available engine (including Tor index and Archive.org)
    to surface buried, deleted, and de-indexed content.

    Request JSON:
        {
            "query":          "...",   // required
            "max_per_engine": 10       // optional, default 10
        }

    Response: same shape as /query
    """
    try:
        body = request.get_json() or {}
        q = (body.get("query") or "").strip()
        if not q:
            return jsonify({"success": False, "error": "Query parameter 'query' is required"}), 400

        max_per = int(body.get("max_per_engine", 10))
        max_per = max(1, min(max_per, 20))

        logger.info(f"Deep search query: {q!r}  max_per={max_per}")
        agg = _get_aggregator()
        result = agg.deep_search(q, max_per_engine=max_per)

        return jsonify({"success": True, "data": result})

    except Exception as exc:
        logger.error(f"deep_query error: {exc}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500


# ---------------------------------------------------------------------------
# /api/search/fetch  – fetch full article text from a URL
# ---------------------------------------------------------------------------

@search_bp.route("/fetch", methods=["POST"])
def fetch_article():
    """
    Fetch and extract the full text of an article URL, stripping ads and
    navigation noise.

    Request JSON:
        { "url": "https://..." }

    Response:
        {
            "success": true,
            "data": {
                "url": "...",
                "title": "...",
                "content": "...",
                "source_name": "...",
                "credibility_tier": "...",
                "published_at": "...",
                "author": "...",
                "content_length": 4200
            }
        }
    """
    try:
        body = request.get_json() or {}
        url = (body.get("url") or "").strip()
        if not url:
            return jsonify({"success": False, "error": "Field 'url' is required"}), 400

        article = NewsFetcher.fetch_url(url)

        return jsonify({"success": True, "data": article.to_dict()})

    except Exception as exc:
        logger.error(f"fetch_article error: {exc}\n{traceback.format_exc()}")
        return jsonify({"success": False, "error": str(exc), "traceback": traceback.format_exc()}), 500
