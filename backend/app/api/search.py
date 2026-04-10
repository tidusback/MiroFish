"""
Search API Blueprint
====================
Endpoints:
  GET  /api/search/providers           – list providers with availability
  POST /api/search/                    – run a search
  GET  /api/search/suggest?q=...       – autocomplete suggestions
  GET  /api/search/export?...          – download results as JSON or CSV
  POST /api/search/cache/clear         – clear result cache (admin)
"""

import csv
import io
import json
import logging

from flask import Response, current_app, jsonify, request, stream_with_context

from . import search_bp
from ..services.search_engine import (
    DEFAULT_PROVIDERS,
    DEEP_PROVIDERS,
    SearchEngine,
    _PROVIDER_REGISTRY,
)

logger = logging.getLogger("mirofish.api.search")

_engine: SearchEngine | None = None


def _get_engine() -> SearchEngine:
    global _engine
    if _engine is None:
        _engine = SearchEngine.from_config(current_app.config)
    return _engine


# ── GET /api/search/providers ─────────────────────────────────────────────────

@search_bp.route("/providers", methods=["GET"])
def list_providers():
    engine = _get_engine()
    return jsonify({
        "providers": engine.get_providers_info(),
        "default_providers": DEFAULT_PROVIDERS,
        "deep_providers": DEEP_PROVIDERS,
    })


# ── POST /api/search/ ─────────────────────────────────────────────────────────

@search_bp.route("/", methods=["POST"])
def search():
    """
    Run an uncensored meta-search.

    Request body (JSON):
      {
        "query":            "search query",             (required)
        "providers":        ["duckduckgo", ...],        (optional)
        "max_per_provider": 10,                         (optional, 1-50)
        "page":             1,                          (optional)
        "mode":             "default" | "deep",         (optional)
        "date_from":        "2020-01-01",               (optional, YYYY-MM-DD)
        "date_to":          "2024-12-31",               (optional, YYYY-MM-DD)
        "no_cache":         false                       (optional, bypass cache)
      }
    """
    body = request.get_json(silent=True) or {}

    query = (body.get("query") or "").strip()
    if not query:
        return jsonify({"error": "query is required"}), 400

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

    date_from = (body.get("date_from") or "").strip() or None
    date_to   = (body.get("date_to")   or "").strip() or None
    no_cache  = bool(body.get("no_cache", False))

    logger.info(
        f"Search: query={query!r} providers={providers} "
        f"max={max_per} page={page} date={date_from}..{date_to}"
    )

    engine = _get_engine()
    result = engine.search(
        query=query,
        providers=providers,
        max_per_provider=max_per,
        page=page,
        date_from=date_from,
        date_to=date_to,
        use_cache=not no_cache,
    )

    return jsonify(result)


# ── GET /api/search/suggest ───────────────────────────────────────────────────

@search_bp.route("/suggest", methods=["GET"])
def suggest():
    """DuckDuckGo autocomplete suggestions."""
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
        suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
        return jsonify({"suggestions": suggestions[:10]})
    except Exception as exc:
        logger.debug(f"Suggest failed: {exc}")
        return jsonify({"suggestions": []})


# ── GET /api/search/export ────────────────────────────────────────────────────

@search_bp.route("/export", methods=["GET"])
def export_results():
    """
    Re-run a search and stream the results as a downloadable file.

    Query params:
      q          – required search query
      fmt        – "json" (default) or "csv"
      providers  – comma-separated provider IDs (optional)
      mode       – "default" | "deep" (optional)
      date_from  – YYYY-MM-DD (optional)
      date_to    – YYYY-MM-DD (optional)
      max        – max results per provider (default 20)
    """
    query = (request.args.get("q") or "").strip()
    if not query:
        return jsonify({"error": "q parameter is required"}), 400

    fmt = (request.args.get("fmt") or "json").lower()
    if fmt not in ("json", "csv"):
        return jsonify({"error": "fmt must be 'json' or 'csv'"}), 400

    mode = request.args.get("mode", "default")
    raw_providers = request.args.get("providers", "")
    if raw_providers:
        providers = [p.strip() for p in raw_providers.split(",") if p.strip() in _PROVIDER_REGISTRY]
    elif mode == "deep":
        providers = DEEP_PROVIDERS
    else:
        providers = DEFAULT_PROVIDERS

    max_per = int(request.args.get("max") or 20)
    max_per = max(1, min(max_per, 50))

    date_from = (request.args.get("date_from") or "").strip() or None
    date_to   = (request.args.get("date_to")   or "").strip() or None

    engine = _get_engine()
    result = engine.search(
        query=query,
        providers=providers,
        max_per_provider=max_per,
        date_from=date_from,
        date_to=date_to,
        use_cache=True,
    )
    results = result.get("results", [])

    safe_q = "".join(c for c in query[:40] if c.isalnum() or c in " -_").strip().replace(" ", "_")

    if fmt == "json":
        content = json.dumps(result, ensure_ascii=False, indent=2)
        return Response(
            content,
            mimetype="application/json",
            headers={"Content-Disposition": f'attachment; filename="mirofish_{safe_q}.json"'},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=["title", "url", "source", "source_type", "snippet",
                    "published_at", "author"],
        extrasaction="ignore",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    for row in results:
        writer.writerow({
            "title":       row.get("title", ""),
            "url":         row.get("url", ""),
            "source":      row.get("source", ""),
            "source_type": row.get("source_type", ""),
            "snippet":     row.get("snippet", ""),
            "published_at":row.get("published_at", ""),
            "author":      row.get("author", ""),
        })

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="mirofish_{safe_q}.csv"'},
    )


# ── POST /api/search/cache/clear ─────────────────────────────────────────────

@search_bp.route("/cache/clear", methods=["POST"])
def clear_cache():
    """Clear the in-memory result cache."""
    engine = _get_engine()
    engine.clear_cache()
    return jsonify({"status": "ok", "message": "Search cache cleared"})
