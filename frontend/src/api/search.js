/**
 * Uncensored Meta-Search Engine – API Client
 */

import axios from 'axios'

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001') + '/api/search'

/** List all available search providers with their status. */
export async function getProviders() {
  const resp = await axios.get(`${BASE}/providers`)
  return resp.data
}

/**
 * Run an uncensored meta-search.
 *
 * @param {string}        query
 * @param {string[]|null} providers       - provider IDs (null = use server default)
 * @param {number}        maxPerProvider
 * @param {number}        page
 * @param {string}        mode            - "default" | "deep"
 * @param {string|null}   dateFrom        - YYYY-MM-DD
 * @param {string|null}   dateTo          - YYYY-MM-DD
 * @param {boolean}       noCache         - bypass cache
 */
export async function search({
  query,
  providers = null,
  maxPerProvider = 10,
  page = 1,
  mode = 'default',
  dateFrom = null,
  dateTo = null,
  noCache = false,
}) {
  const body = {
    query,
    max_per_provider: maxPerProvider,
    page,
    mode,
    no_cache: noCache,
  }
  if (providers && providers.length > 0) body.providers = providers
  if (dateFrom) body.date_from = dateFrom
  if (dateTo)   body.date_to   = dateTo

  const resp = await axios.post(`${BASE}/`, body, { timeout: 35000 })
  return resp.data
}

/**
 * Get autocomplete suggestions for a partial query.
 */
export async function suggest(q) {
  if (!q || q.length < 2) return []
  try {
    const resp = await axios.get(`${BASE}/suggest`, { params: { q }, timeout: 5000 })
    return resp.data.suggestions || []
  } catch {
    return []
  }
}

/**
 * Send search results to the LLM for investigative analysis.
 * Returns null + logs if LLM is not configured.
 *
 * @param {string} query
 * @param {Array}  results   – from search()
 * @param {number} maxN      – max results to analyze (default 20)
 */
export async function analyzeResults({ query, results, maxN = 20 }) {
  const resp = await axios.post(
    `${BASE}/analyze`,
    { query, results, max_results_to_analyze: maxN },
    { timeout: 60000 }
  )
  return resp.data
}

/**
 * Build a URL to download search results.
 *
 * @param {string}   query
 * @param {string}   fmt       - "json" | "csv"
 * @param {string[]} providers
 * @param {string}   mode
 * @param {string}   dateFrom
 * @param {string}   dateTo
 */
export function exportUrl({ query, fmt = 'json', providers = [], mode = 'default', dateFrom = '', dateTo = '' }) {
  const params = new URLSearchParams({ q: query, fmt, mode })
  if (providers.length) params.set('providers', providers.join(','))
  if (dateFrom) params.set('date_from', dateFrom)
  if (dateTo)   params.set('date_to',   dateTo)
  return `${BASE}/export?${params.toString()}`
}
