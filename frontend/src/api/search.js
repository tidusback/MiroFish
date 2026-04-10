/**
 * Uncensored Meta-Search Engine – API Client
 */

import axios from 'axios'

const BASE = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5001') + '/api/search'

/**
 * List all available search providers with their status.
 */
export async function getProviders() {
  const resp = await axios.get(`${BASE}/providers`)
  return resp.data
}

/**
 * Run an uncensored meta-search.
 *
 * @param {string}   query            - Search query
 * @param {string[]} providers        - Provider IDs to use (optional)
 * @param {number}   maxPerProvider   - Max results per provider (default 10)
 * @param {number}   page             - Page number (default 1)
 * @param {string}   mode             - "default" | "deep"
 */
export async function search({ query, providers = null, maxPerProvider = 10, page = 1, mode = 'default' }) {
  const body = {
    query,
    max_per_provider: maxPerProvider,
    page,
    mode,
  }
  if (providers && providers.length > 0) {
    body.providers = providers
  }

  const resp = await axios.post(`${BASE}/`, body, { timeout: 35000 })
  return resp.data
}

/**
 * Get autocomplete suggestions for a partial query.
 *
 * @param {string} q - Partial query
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
