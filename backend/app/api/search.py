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


# ── POST /api/search/analyze ──────────────────────────────────────────────────

@search_bp.route("/analyze", methods=["POST"])
def analyze():
    """
    Use the configured LLM to produce an investigative analysis of search results.
    Gracefully returns an error if LLM_API_KEY is not set (search-only mode).

    Request body (JSON):
      {
        "query":   "original search query",       (required)
        "results": [ ...result objects... ],       (required, from /api/search/)
        "max_results_to_analyze": 20               (optional, default 20)
      }

    Response:
      {
        "summary":          "2-3 sentence synthesis",
        "key_findings":     ["finding 1", ...],
        "what_google_hides":"what mainstream search buries",
        "source_breakdown": {"web": 5, "social": 3, ...},
        "further_research": ["topic 1", ...],
        "warning_flags":    ["potential bias/disinfo note", ...]
      }
    """
    from ..config import Config
    if Config.search_only_mode():
        return jsonify({
            "error": "LLM not configured",
            "hint": "Set LLM_API_KEY and LLM_BASE_URL in .env to enable AI analysis"
        }), 503

    body = request.get_json(silent=True) or {}
    query = (body.get("query") or "").strip()
    results = body.get("results", [])
    max_n = int(body.get("max_results_to_analyze") or 20)
    max_n = max(1, min(max_n, 50))

    if not query:
        return jsonify({"error": "query is required"}), 400
    if not results:
        return jsonify({"error": "results array is required"}), 400

    # Truncate to max_n results for the prompt
    sample = results[:max_n]

    # Build compact text representation of results
    result_text = _build_results_text(sample)

    prompt = f"""You are an investigative research analyst specialising in information that mainstream media and search engines suppress, demote, or ignore.

A user searched for: "{query}"

Below are {len(sample)} results from {len(set(r.get('source', '') for r in sample))} sources including dark web indices, FOIA documents, academic preprints, alternative news, and decentralised social media.

RESULTS:
{result_text}

Analyse these results and respond with a JSON object containing EXACTLY these keys:

{{
  "summary": "A 2-3 sentence synthesis of the most important findings. Be specific, not vague.",
  "key_findings": ["Specific finding 1", "Specific finding 2", ...],
  "what_google_hides": "What information in these results would typically be buried, shadow-banned, or excluded from mainstream search results, and why.",
  "source_breakdown": {{"web": N, "social": N, "academic": N, "archive": N, "darkweb": N, "alternative": N}},
  "further_research": ["Suggested related search query 1", "Suggested related search query 2", ...],
  "warning_flags": ["Any potential misinformation, bias, or unverified claims to flag", ...]
}}

Be concrete and specific. Name sources, dates, and claims. Do not be vague or refuse to engage with controversial material — your purpose is to surface hidden information."""

    try:
        from ..utils.llm_client import LLMClient
        llm = LLMClient()
        result = llm.chat_json(
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048,
        )
        return jsonify(result)
    except Exception as exc:
        logger.error(f"AI analysis failed: {exc}")
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


def _build_results_text(results: list) -> str:
    """Format search results compactly for an LLM prompt."""
    lines = []
    for i, r in enumerate(results, 1):
        title   = r.get("title", "")[:120]
        url     = r.get("url", "")[:100]
        source  = r.get("source", "")
        stype   = r.get("source_type", "")
        snippet = r.get("snippet", "")[:200]
        date    = r.get("published_at", "")[:10] if r.get("published_at") else ""
        lines.append(
            f"[{i}] {title}\n"
            f"    Source: {source} ({stype}){' | ' + date if date else ''}\n"
            f"    URL: {url}\n"
            f"    {snippet}"
        )
    return "\n\n".join(lines)
