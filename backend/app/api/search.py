"""
Search API Blueprint
====================
Endpoints:
  GET  /api/search/providers        – list all providers with availability status
  POST /api/search/                 – run a search query
  GET  /api/search/suggest          – autocomplete / query suggestion (DDG Instant Answers)
"""

import logging

from flask import current_app, jsonify, request

from . import search_bp
from ..services.search_engine import (
    DEFAULT_PROVIDERS,
    DEEP_PROVIDERS,
    SearchEngine,
    _PROVIDER_REGISTRY,
)

logger = logging.getLogger("mirofish.api.search")

# Module-level engine singleton (initialised lazily per app context)
_engine: SearchEngine | None = None


def _get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine.from_config(current_app.config)
    return _engine


# ---------------------------------------------------------------------------
# GET /api/search/providers
# ---------------------------------------------------------------------------

@search_bp.route("/providers", methods=["GET"])
def list_providers():
    """Return all registered providers with availability status."""
    engine = _get_engine()
    return jsonify({
        "providers": engine.get_providers_info(),
        "default_providers": DEFAULT_PROVIDERS,
        "deep_providers": DEEP_PROVIDERS,
    })


# ---------------------------------------------------------------------------
# POST /api/search/
# ---------------------------------------------------------------------------

@search_bp.route("/", methods=["POST"])
def search():
    """
    Execute an uncensored meta-search.

    Request body (JSON):
      {
        "query":            "your search query",           (required)
        "providers":        ["duckduckgo", "reddit", ...], (optional, default set)
        "max_per_provider": 10,                            (optional, 1-50)
        "page":             1,                             (optional)
        "mode":             "default" | "deep",            (optional)
      }

    Response:
      {
        "results": [...],
        "total": int,
        "providers_used": [...],
        "providers_failed": [...],
        "providers_skipped": [...],
        "query": str,
        "took_ms": int,
      }
    """
    body = request.get_json(silent=True) or {}

    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

    # Determine provider list
    mode = body.get("mode", "default")
    if body.get("providers"):
        providers = [p for p in body["providers"] if p in _PROVIDER_REGISTRY]
    elif mode == "deep":
        providers = DEEP_PROVIDERS
    else:
        providers = DEFAULT_PROVIDERS

    max_per = int(body.get("max_per_provider") or 10)
    max_per = max(1, min(max_per, 50))

    page = int(body.get("page") or 1)
    page = max(1, page)

    logger.info(
        f"Search: query={query!r} providers={providers} max={max_per} page={page}"
    )

    engine = _get_engine()
    result = engine.search(
        query=query,
        providers=providers,
        max_per_provider=max_per,
        page=page,
    )

    return jsonify(result)


# ---------------------------------------------------------------------------
# GET /api/search/suggest?q=...
# ---------------------------------------------------------------------------

@search_bp.route("/suggest", methods=["GET"])
def suggest():
    """
    Quick suggestions using DuckDuckGo Instant Answers API.
    Returns a list of suggested completions for the given partial query.
    """
    q = (request.args.get("q") or "").strip()
    if not q:
        return jsonify({"suggestions": []})

    try:
        import requests as req
        resp = req.get(
            "https://ac.duckduckgo.com/ac/",
            params={"q": q, "type": "list"},
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        # DDG returns [query, [suggestion1, suggestion2, ...]]
        suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
        return jsonify({"suggestions": suggestions[:10]})
    except Exception as exc:
        logger.debug(f"Suggest failed: {exc}")
        return jsonify({"suggestions": []})
