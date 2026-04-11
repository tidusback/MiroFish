<template>
  <div class="search-root" @keydown.escape="clearSuggestions; showHistory = false">

    <!-- Toast notifications -->
    <transition name="toast-fade">
      <div v-if="shareToast || feedToast" class="toast">
        {{ feedToast ? '→ Sent to MiroFish' : '✓ Link copied' }}
      </div>
    </transition>

    <!-- ── NAV ──────────────────────────────────────────────────── -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand">MIROFISH</router-link>
      <div class="nav-right">
        <span class="nav-tag">DEEP SEARCH</span>
        <span class="nav-hint">Press <kbd>/</kbd> to search</span>
      </div>
    </nav>

    <!-- ── SEARCH BAR ───────────────────────────────────────────── -->
    <section class="hero">
      <div class="hero-pills">
        <span class="pill">AD-FREE</span>
        <span class="pill pill--dark">UNCENSORED</span>
        <span class="pill pill--accent">{{ providerCount }}+ SOURCES</span>
        <span v-if="lastResult?.cached" class="pill pill--cached">CACHED</span>
      </div>
      <h1 class="hero-title">Search Without Walls</h1>
      <p class="hero-sub">
        Web · Social · Academic · Archive · Dark Web · Courts · Alternative News · Corporate Records
      </p>

      <form class="search-form" @submit.prevent="runSearch">
        <div class="search-input-wrap" :class="{ focused: inputFocused }">
          <input
            ref="inputRef"
            v-model="query"
            class="search-input"
            placeholder="Search anything…"
            autocomplete="off"
            spellcheck="false"
            @focus="onInputFocus"
            @blur="onInputBlur"
            @input="onInputChange; showHistory = false"
            @keydown.down.prevent="moveSuggestion(1)"
            @keydown.up.prevent="moveSuggestion(-1)"
            @keydown.enter.prevent="handleEnter"
          />
          <button type="button" v-if="query" class="clear-btn" @click="clearQuery" title="Clear">✕</button>
          <button
            type="button"
            v-if="searchHistory.length"
            class="history-toggle-btn"
            :class="{ active: showHistory }"
            @click.prevent="showHistory = !showHistory"
            title="Recent searches"
          >◷</button>
          <button type="submit" class="search-btn" :disabled="searching || !query.trim()">
            <span v-if="!searching">SEARCH</span>
            <span v-else class="spin">◌</span>
          </button>
        </div>

        <!-- Autocomplete dropdown -->
        <ul v-if="suggestions.length && !searching" class="suggestions">
          <li
            v-for="(s, i) in suggestions"
            :key="i"
            :class="{ active: i === suggestionIdx }"
            @mousedown.prevent="acceptSuggestion(s)"
          >{{ s }}</li>
        </ul>

        <!-- Search history dropdown -->
        <div v-if="showHistory && searchHistory.length && !suggestions.length" class="history-dropdown">
          <div class="history-header">
            <span>Recent searches</span>
            <button class="history-clear-btn" @mousedown.prevent="clearHistory">Clear all</button>
          </div>
          <ul class="history-list">
            <li v-for="(h, i) in searchHistory" :key="h.ts" class="history-item">
              <button class="history-query" @mousedown.prevent="runFromHistory(h.query)">
                <span class="history-icon">◷</span>
                <span class="history-text">{{ h.query }}</span>
                <span class="history-time">{{ formatHistoryTs(h.ts) }}</span>
              </button>
              <button class="history-remove" @mousedown.prevent="removeFromHistory(i)" title="Remove">✕</button>
            </li>
          </ul>
        </div>
      </form>

      <!-- Row: deep mode + date range -->
      <div class="options-row">
        <label class="mode-toggle">
          <input type="checkbox" v-model="deepMode" />
          <span class="toggle-track"><span class="toggle-thumb" /></span>
          <span class="mode-label">
            Deep mode
            <span class="mode-hint">(+ dark web, courts, corporate)</span>
          </span>
        </label>

        <div class="date-range">
          <input
            type="date"
            v-model="dateFrom"
            class="date-input"
            title="From date"
            placeholder="From"
          />
          <span class="date-sep">→</span>
          <input
            type="date"
            v-model="dateTo"
            class="date-input"
            title="To date"
          />
          <button v-if="dateFrom || dateTo" class="clear-dates" @click="dateFrom = dateTo = ''" title="Clear dates">✕</button>
        </div>

        <label class="mode-toggle">
          <input type="checkbox" v-model="compactMode" />
          <span class="toggle-track"><span class="toggle-thumb" /></span>
          <span class="mode-label">Compact</span>
        </label>
      </div>
    </section>

    <!-- ── PROVIDER CHIPS ────────────────────────────────────────── -->
    <section v-if="availableProviders.length" class="providers-section">
      <div class="providers-label">
        Sources
        <button class="toggle-all-btn" @click="toggleAll">
          {{ allSelected ? 'Deselect all' : 'Select all' }}
        </button>
      </div>
      <div class="provider-chips">
        <button
          v-for="p in availableProviders"
          :key="p.id"
          class="chip"
          :class="{
            'chip--active': selectedProviders.includes(p.id),
            [`chip--${p.source_type}`]: true,
          }"
          @click="toggleProvider(p.id)"
          :title="p.source_type"
        >
          <span class="chip-dot" />{{ p.name }}
        </button>
      </div>
      <p v-if="unavailableProviders.length" class="providers-note">
        {{ unavailableProviders.map(p => p.name).join(', ') }} require API keys — add them to .env
      </p>
    </section>

    <!-- ── RESULTS ───────────────────────────────────────────────── -->
    <section v-if="hasSearched" class="results-section">

      <!-- Stats + export bar -->
      <div class="stats-bar">
        <template v-if="!searching">
          <span class="stat-count">{{ results.length }} results</span>
          <span class="stat-sep">·</span>
          <span class="stat-time">{{ lastResult?.took_ms }}ms</span>
          <span class="stat-sep">·</span>
          <span class="stat-sources">{{ usedProviders.join(', ') || '—' }}</span>
          <span v-if="failedProviders.length" class="stat-failed">
            · {{ failedProviders.length }} failed
          </span>
          <span v-if="lastResult?.cached" class="stat-cached">· cached</span>
          <div class="stats-right">
            <a :href="exportHref('json')" class="export-btn" download>↓ JSON</a>
            <a :href="exportHref('csv')"  class="export-btn" download>↓ CSV</a>
            <button
              class="export-btn action-btn"
              :class="{ 'action-btn--active': showAnalysis }"
              @click="runAnalysis"
              :disabled="analyzing"
              title="AI investigative analysis"
            >{{ analyzing ? '◌' : 'AI' }}</button>
            <button
              class="export-btn action-btn action-btn--feed"
              @click="feedToMiroFish"
              title="Send results to MiroFish for simulation"
            >→ MiroFish</button>
            <button
              class="export-btn action-btn"
              :class="{ 'action-btn--copied': shareToast }"
              @click="shareUrl"
              title="Copy shareable link"
            >{{ shareToast ? '✓ Copied' : '⎘ Share' }}</button>
          </div>
        </template>
        <template v-else>
          <span class="searching-msg">Searching across {{ pendingCount }} sources…</span>
        </template>
      </div>

      <!-- Source type tabs -->
      <div class="type-tabs">
        <button
          v-for="tab in typeTabs"
          :key="tab.value"
          class="type-tab"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}<span class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- AI Analysis Panel -->
      <transition name="slide-down">
        <div v-if="showAnalysis" class="analysis-panel">
          <div class="analysis-header">
            <span class="analysis-title">AI Investigative Analysis</span>
            <button class="analysis-close" @click="showAnalysis = false">✕</button>
          </div>
          <div v-if="analyzing" class="analysis-loading">
            <span class="spin">◌</span> Analysing {{ results.length }} results across all sources…
          </div>
          <div v-else-if="analysisError" class="analysis-error">{{ analysisError }}</div>
          <div v-else-if="analysis" class="analysis-body">
            <div class="analysis-section" v-if="analysis.summary">
              <div class="analysis-label">SUMMARY</div>
              <p class="analysis-text">{{ analysis.summary }}</p>
            </div>
            <div class="analysis-section" v-if="analysis.key_findings?.length">
              <div class="analysis-label">KEY FINDINGS</div>
              <ul class="analysis-list">
                <li v-for="f in analysis.key_findings" :key="f">{{ f }}</li>
              </ul>
            </div>
            <div class="analysis-section" v-if="analysis.what_google_hides">
              <div class="analysis-label">WHAT MAINSTREAM SEARCH BURIES</div>
              <p class="analysis-text analysis-text--highlight">{{ analysis.what_google_hides }}</p>
            </div>
            <div class="analysis-section" v-if="analysis.further_research?.length">
              <div class="analysis-label">DIG DEEPER</div>
              <div class="further-tags">
                <button
                  v-for="q in analysis.further_research"
                  :key="q"
                  class="further-tag"
                  @click="runFromHistory(q)"
                >{{ q }}</button>
              </div>
            </div>
            <div class="analysis-section" v-if="analysis.warning_flags?.length">
              <div class="analysis-label">WARNING FLAGS</div>
              <ul class="analysis-list analysis-list--warn">
                <li v-for="w in analysis.warning_flags" :key="w">⚠ {{ w }}</li>
              </ul>
            </div>
          </div>
        </div>
      </transition>

      <!-- Skeleton loader -->
      <div v-if="searching" class="skeleton-list">
        <div v-for="i in 8" :key="i" class="skeleton-card" />
      </div>

      <!-- Result cards -->
      <transition-group v-else name="fade" tag="div" class="result-list">
        <article
          v-for="(r, idx) in filteredResults"
          :key="r.url + idx"
          class="result-card"
          :class="[`result-card--${r.source_type}`, { 'result-card--compact': compactMode }]"
        >
          <!-- Source meta row -->
          <div class="result-meta">
            <span class="source-badge" :class="`badge--${r.source_type}`">{{ sourceLabel(r.source_type) }}</span>
            <span class="source-name">{{ r.source }}</span>
            <span v-if="r.published_at" class="result-date">{{ formatDate(r.published_at) }}</span>
            <span v-if="r.author" class="result-author">by {{ r.author }}</span>
          </div>

          <!-- Title -->
          <h3 class="result-title">
            <a :href="r.url" target="_blank" rel="noopener noreferrer">{{ r.title || r.url }}</a>
            <span v-if="r.source_type === 'darkweb'" class="onion-tag" title="Tor .onion — requires Tor Browser">🧅 .onion</span>
          </h3>

          <!-- URL -->
          <div class="result-url">{{ truncateUrl(r.url) }}</div>

          <!-- Snippet -->
          <p v-if="r.snippet" class="result-snippet">{{ r.snippet }}</p>

          <!-- Action row: extra pills + archive link -->
          <div class="result-actions">
            <div class="result-extra">
              <span v-if="r.extra?.stars"        class="extra-pill">★ {{ r.extra.stars }}</span>
              <span v-if="r.extra?.score"         class="extra-pill">↑ {{ r.extra.score }}</span>
              <span v-if="r.extra?.num_comments"  class="extra-pill">💬 {{ r.extra.num_comments }}</span>
              <span v-if="r.extra?.subreddit"     class="extra-pill">{{ r.extra.subreddit }}</span>
              <span v-if="r.extra?.court"         class="extra-pill">⚖ {{ r.extra.court }}</span>
              <span v-if="r.extra?.citation"      class="extra-pill">{{ r.extra.citation }}</span>
              <span v-if="r.extra?.company_number" class="extra-pill">Co.# {{ r.extra.company_number }}</span>
              <span v-if="r.extra?.jurisdiction"  class="extra-pill">{{ r.extra.jurisdiction?.toUpperCase() }}</span>
              <template v-if="r.extra?.categories?.length">
                <span class="extra-pill">{{ r.extra.categories.slice(0,2).join(' · ') }}</span>
              </template>
              <span v-if="r.extra?.open_access"   class="extra-pill extra-pill--green">Open Access</span>
              <span v-if="r.extra?.doi"            class="extra-pill">DOI</span>
              <span v-if="r.extra?.language && r.extra.language !== 'English'" class="extra-pill">{{ r.extra.language }}</span>
              <span v-if="r.extra?.country"        class="extra-pill">{{ r.extra.country }}</span>
            </div>

            <!-- Archive links -->
            <div class="result-archive-links" v-if="r.source_type !== 'darkweb'">
              <a
                :href="`https://web.archive.org/web/*/${encodeURIComponent(r.url)}`"
                target="_blank"
                rel="noopener noreferrer"
                class="archive-link"
                title="All snapshots on Wayback Machine"
              >archive ↗</a>
              <a
                :href="`https://web.archive.org/web/${r.url}`"
                target="_blank"
                rel="noopener noreferrer"
                class="archive-link"
                title="Latest cached version"
              >cached ↗</a>
            </div>
          </div>
        </article>
      </transition-group>

      <!-- Empty state -->
      <div v-if="!searching && filteredResults.length === 0" class="empty-state">
        <div class="empty-icon">∅</div>
        <p v-if="results.length === 0">No results found. Try different keywords, enable more sources, or switch to Deep mode.</p>
        <p v-else>No results in this category. Switch tabs or select All.</p>
      </div>

      <!-- Load more -->
      <div v-if="!searching && filteredResults.length > 0" class="load-more-row">
        <button class="load-more-btn" :disabled="searching" @click="loadMore">
          Load page {{ currentPage + 1 }} →
        </button>
      </div>
    </section>

    <!-- ── FOOTER ────────────────────────────────────────────────── -->
    <footer class="search-footer">
      <span>MiroFish Deep Search</span>
      <span class="sep">·</span>
      <span>No ads. No tracking. No filter bubbles.</span>
      <span class="sep">·</span>
      <a href="https://github.com/666ghj/MiroFish" target="_blank" rel="noopener">GitHub ↗</a>
    </footer>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { getProviders, search as apiSearch, suggest as apiSuggest, exportUrl, analyzeResults } from '../api/search'
import { setPendingUpload } from '../store/pendingUpload'

// ── State ─────────────────────────────────────────────────────────────────────

const query    = ref('')
const dateFrom = ref('')
const dateTo   = ref('')
const searching    = ref(false)
const hasSearched  = ref(false)
const results      = ref([])
const lastResult   = ref(null)
const usedProviders   = ref([])
const failedProviders = ref([])
const deepMode  = ref(false)
const activeTab = ref('all')
const currentPage = ref(1)
const inputFocused = ref(false)

const suggestions   = ref([])
const suggestionIdx = ref(-1)
const suggestTimer  = ref(null)

const availableProviders   = ref([])
const unavailableProviders = ref([])
const selectedProviders    = ref([])

const inputRef = ref(null)

const router      = useRouter()
const compactMode = ref(false)
const shareToast  = ref(false)
const feedToast   = ref(false)

const HISTORY_KEY   = 'mf_search_history'
const searchHistory = ref([])
const showHistory   = ref(false)

const analyzing     = ref(false)
const analysis      = ref(null)
const showAnalysis  = ref(false)
const analysisError = ref('')

// ── Provider loading ──────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    const data = await getProviders()
    availableProviders.value   = (data.providers || []).filter(p => p.available)
    unavailableProviders.value = (data.providers || []).filter(p => !p.available)
    selectedProviders.value    = availableProviders.value.map(p => p.id)
  } catch (e) {
    console.warn('Could not load providers:', e)
  }
  searchHistory.value = _loadHistory()
  compactMode.value   = localStorage.getItem('mf_compact') === '1'
  inputRef.value?.focus()
})

// Global "/" shortcut to focus search
function onKeyDown(e) {
  if (e.key === '/' && document.activeElement !== inputRef.value && !['INPUT','TEXTAREA'].includes(document.activeElement?.tagName)) {
    e.preventDefault()
    inputRef.value?.focus()
  }
}
onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))

watch(compactMode, v => localStorage.setItem('mf_compact', v ? '1' : '0'))

// ── Computed ──────────────────────────────────────────────────────────────────

const providerCount = computed(() => availableProviders.value.length || 15)
const pendingCount  = computed(() => selectedProviders.value.length)
const allSelected   = computed(() =>
  availableProviders.value.every(p => selectedProviders.value.includes(p.id))
)

const typeTabs = computed(() => {
  const counts = {}
  for (const r of results.value) counts[r.source_type] = (counts[r.source_type] || 0) + 1
  const tabs = [{ label: 'All', value: 'all', count: results.value.length }]
  const labels = {
    web: 'Web', social: 'Social', academic: 'Academic',
    archive: 'Archive', darkweb: 'Dark Web', code: 'Code',
    encyclopedia: 'Wiki', alternative: 'Alt / Indie',
  }
  for (const [type, label] of Object.entries(labels)) {
    if (counts[type]) tabs.push({ label, value: type, count: counts[type] })
  }
  return tabs
})

const filteredResults = computed(() => {
  if (activeTab.value === 'all') return results.value
  return results.value.filter(r => r.source_type === activeTab.value)
})

// ── Search ────────────────────────────────────────────────────────────────────

async function runSearch(resetPage = true) {
  const q = query.value.trim()
  if (!q || searching.value) return

  clearSuggestions()
  searching.value = true
  hasSearched.value = true
  if (resetPage) {
    activeTab.value = 'all'
    currentPage.value = 1
    showHistory.value = false
    saveToHistory(q)
    analysis.value = null
    showAnalysis.value = false
  }

  try {
    const providers = selectedProviders.value.length ? selectedProviders.value : null
    const data = await apiSearch({
      query: q,
      providers,
      maxPerProvider: 12,
      page: currentPage.value,
      mode: deepMode.value ? 'deep' : 'default',
      dateFrom: dateFrom.value || null,
      dateTo: dateTo.value || null,
    })

    if (resetPage) {
      results.value = data.results || []
    } else {
      // Append deduplicated new results for pagination
      const existing = new Set(results.value.map(r => r.url))
      const fresh = (data.results || []).filter(r => !existing.has(r.url))
      results.value = [...results.value, ...fresh]
    }

    lastResult.value       = data
    usedProviders.value    = data.providers_used || []
    failedProviders.value  = data.providers_failed || []
  } catch (err) {
    console.error('Search error:', err)
    results.value = []
  } finally {
    searching.value = false
  }
}

async function loadMore() {
  currentPage.value++
  await runSearch(false)
}

// ── Autocomplete ──────────────────────────────────────────────────────────────

function onInputChange() {
  suggestionIdx.value = -1
  clearTimeout(suggestTimer.value)
  if (query.value.length < 2) { suggestions.value = []; return }
  suggestTimer.value = setTimeout(async () => {
    suggestions.value = await apiSuggest(query.value)
  }, 260)
}

function moveSuggestion(dir) {
  if (!suggestions.value.length) return
  suggestionIdx.value = Math.max(-1, Math.min(suggestions.value.length - 1, suggestionIdx.value + dir))
  if (suggestionIdx.value >= 0) query.value = suggestions.value[suggestionIdx.value]
}

function handleEnter() {
  if (suggestionIdx.value >= 0 && suggestions.value[suggestionIdx.value]) {
    query.value = suggestions.value[suggestionIdx.value]
    clearSuggestions()
  }
  runSearch()
}

function acceptSuggestion(s) {
  query.value = s
  clearSuggestions()
  runSearch()
}

function clearSuggestions() {
  suggestions.value = []
  suggestionIdx.value = -1
}

function clearQuery() {
  query.value = ''
  suggestions.value = []
  inputRef.value?.focus()
}

// ── Provider controls ─────────────────────────────────────────────────────────

function toggleProvider(id) {
  const idx = selectedProviders.value.indexOf(id)
  if (idx === -1) {
    selectedProviders.value.push(id)
  } else {
    if (selectedProviders.value.length === 1) return
    selectedProviders.value.splice(idx, 1)
  }
}

function toggleAll() {
  if (allSelected.value) {
    if (availableProviders.value.length > 0)
      selectedProviders.value = [availableProviders.value[0].id]
  } else {
    selectedProviders.value = availableProviders.value.map(p => p.id)
  }
}

// ── Export ────────────────────────────────────────────────────────────────────

function exportHref(fmt) {
  return exportUrl({
    query: query.value,
    fmt,
    providers: selectedProviders.value,
    mode: deepMode.value ? 'deep' : 'default',
    dateFrom: dateFrom.value,
    dateTo: dateTo.value,
  })
}

// ── Display helpers ───────────────────────────────────────────────────────────

function sourceLabel(type) {
  return { web: 'WEB', social: 'SOCIAL', academic: 'ACADEMIC',
           archive: 'ARCHIVE', darkweb: 'DARK WEB', code: 'CODE',
           encyclopedia: 'WIKI', alternative: 'ALT' }[type] || type.toUpperCase()
}

function truncateUrl(url) {
  try {
    const u = new URL(url)
    const path = u.pathname + u.search
    const base = u.hostname.replace(/^www\./, '')
    return base + (path.length > 60 ? path.slice(0, 60) + '…' : path)
  } catch {
    return url.length > 80 ? url.slice(0, 80) + '…' : url
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  try {
    const d = new Date(dateStr)
    if (isNaN(d)) return dateStr.slice(0, 10)
    return d.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' })
  } catch { return dateStr.slice(0, 10) }
}

// ── Search history ────────────────────────────────────────────────────────────

function _loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]') } catch { return [] }
}

function saveToHistory(q) {
  const list = _loadHistory().filter(h => h.query !== q)
  list.unshift({ query: q, ts: Date.now() })
  const trimmed = list.slice(0, 20)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(trimmed))
  searchHistory.value = trimmed
}

function removeFromHistory(idx) {
  searchHistory.value.splice(idx, 1)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(searchHistory.value))
}

function clearHistory() {
  searchHistory.value = []
  localStorage.removeItem(HISTORY_KEY)
  showHistory.value = false
}

function runFromHistory(q) {
  query.value = q
  showHistory.value = false
  runSearch()
}

function formatHistoryTs(ts) {
  const diff = Date.now() - ts
  if (diff < 60000)   return 'just now'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
  return new Date(ts).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function onInputFocus() {
  inputFocused.value = true
  if (!query.value && searchHistory.value.length) showHistory.value = true
}

function onInputBlur() {
  inputFocused.value = false
  setTimeout(() => { showHistory.value = false }, 200)
}

// ── Share URL ─────────────────────────────────────────────────────────────────

async function shareUrl() {
  const params = new URLSearchParams({ q: query.value })
  if (deepMode.value) params.set('deep', '1')
  if (dateFrom.value) params.set('from', dateFrom.value)
  if (dateTo.value)   params.set('to', dateTo.value)
  const url = `${window.location.origin}${window.location.pathname}?${params}`
  try {
    await navigator.clipboard.writeText(url)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = url; document.body.appendChild(ta); ta.select()
    document.execCommand('copy'); document.body.removeChild(ta)
  }
  shareToast.value = true
  setTimeout(() => { shareToast.value = false }, 1800)
}

// ── AI Analysis ───────────────────────────────────────────────────────────────

async function runAnalysis() {
  if (analyzing.value || !results.value.length) return
  showAnalysis.value = true
  analyzing.value    = true
  analysisError.value = ''
  analysis.value      = null
  try {
    const data = await analyzeResults({ query: query.value, results: results.value, maxN: 20 })
    if (data.error) { analysisError.value = data.hint ? `${data.error} — ${data.hint}` : data.error }
    else            { analysis.value = data }
  } catch (err) {
    analysisError.value = 'Analysis failed. Check that LLM_API_KEY is configured in .env.'
  } finally {
    analyzing.value = false
  }
}

// ── Feed to MiroFish ──────────────────────────────────────────────────────────

function feedToMiroFish() {
  const top = results.value.slice(0, 30)
  const newsUrls = top.map(r => r.url).join('\n')
  const insiderSources = top.map(r => ({
    label: `[${(r.source_type || 'WEB').toUpperCase()}] ${r.source}: ${(r.title || r.url).slice(0, 100)}`,
    content: `URL: ${r.url}\n${r.snippet || ''}`.trim(),
  }))
  setPendingUpload([], `Deep Search Results: ${query.value}`, newsUrls, '', insiderSources)
  feedToast.value = true
  setTimeout(() => {
    feedToast.value = false
    router.push('/')
  }, 900)
}
</script>

<style scoped>
/* ── Root ─────────────────────────────────────────────────────────── */
.search-root {
  min-height: 100vh;
  background: #fff;
  color: #000;
  font-family: 'JetBrains Mono', 'Space Grotesk', monospace;
  display: flex;
  flex-direction: column;
}

/* ── Navbar ───────────────────────────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 18px 48px;
  border-bottom: 1px solid #000;
}
.nav-brand {
  font-size: 1rem; font-weight: 700; letter-spacing: .15em;
  color: #000; text-decoration: none;
}
.nav-brand:hover { opacity: .7; }
.nav-right { display: flex; align-items: center; gap: 14px; }
.nav-tag {
  font-size: .65rem; font-weight: 700; letter-spacing: .12em;
  padding: 3px 9px; border: 1px solid #000;
}
.nav-hint { font-size: .7rem; color: #888; }
kbd {
  display: inline-block;
  padding: 1px 5px;
  border: 1px solid #ccc;
  border-radius: 3px;
  font-family: inherit;
  font-size: .7rem;
  background: #f5f5f5;
}

/* ── Hero ─────────────────────────────────────────────────────────── */
.hero {
  padding: 48px 48px 28px;
  max-width: 900px; margin: 0 auto; width: 100%;
}
.hero-pills { display: flex; gap: 7px; flex-wrap: wrap; margin-bottom: 16px; }
.pill {
  font-size: .62rem; font-weight: 700; letter-spacing: .1em;
  padding: 3px 9px; border: 1px solid #000;
}
.pill--dark    { background: #000; color: #fff; }
.pill--accent  { background: #ff6600; color: #fff; border-color: #ff6600; }
.pill--cached  { background: #006600; color: #fff; border-color: #006600; font-size: .6rem; }

.hero-title {
  font-size: clamp(1.8rem, 5vw, 3rem);
  font-weight: 800; line-height: 1.1; margin-bottom: 10px; letter-spacing: -.02em;
}
.hero-sub {
  font-size: .85rem; color: #555; margin-bottom: 28px; line-height: 1.5;
}

/* ── Search form ──────────────────────────────────────────────────── */
.search-form { position: relative; margin-bottom: 16px; }
.search-input-wrap {
  display: flex; border: 2px solid #000;
  transition: box-shadow .15s;
}
.search-input-wrap.focused { box-shadow: 0 0 0 3px rgba(0,0,0,.12); }
.search-input {
  flex: 1; padding: 13px 16px; font-size: 1rem;
  font-family: inherit; border: none; outline: none;
  background: transparent; color: #000;
}
.search-input::placeholder { color: #999; }
.clear-btn {
  background: none; border: none; padding: 0 10px;
  cursor: pointer; color: #999; font-size: .9rem;
}
.clear-btn:hover { color: #000; }
.search-btn {
  padding: 13px 26px; background: #000; color: #fff;
  border: none; font-family: inherit;
  font-size: .75rem; font-weight: 700; letter-spacing: .1em;
  cursor: pointer; transition: background .15s;
}
.search-btn:hover:not(:disabled) { background: #333; }
.search-btn:disabled { opacity: .4; cursor: not-allowed; }
.spin { display: inline-block; animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Suggestions */
.suggestions {
  position: absolute; top: 100%; left: 0; right: 0;
  background: #fff; border: 2px solid #000; border-top: none;
  list-style: none; z-index: 100; margin: 0; padding: 0;
}
.suggestions li {
  padding: 9px 16px; cursor: pointer; font-size: .88rem;
}
.suggestions li:hover, .suggestions li.active { background: #f2f2f2; }

/* Options row */
.options-row {
  display: flex; align-items: center; flex-wrap: wrap; gap: 20px;
}
.mode-toggle {
  display: flex; align-items: center; gap: 9px; cursor: pointer; user-select: none;
}
.mode-toggle input { display: none; }
.toggle-track {
  width: 36px; height: 20px; background: #ccc;
  border-radius: 10px; position: relative; transition: background .2s;
}
.mode-toggle input:checked + .toggle-track { background: #000; }
.toggle-thumb {
  position: absolute; top: 2px; left: 2px;
  width: 16px; height: 16px; background: #fff;
  border-radius: 50%; transition: transform .2s;
}
.mode-toggle input:checked + .toggle-track .toggle-thumb { transform: translateX(16px); }
.mode-label { font-size: .82rem; font-weight: 600; }
.mode-hint  { font-weight: 400; color: #777; font-size: .75rem; }

.date-range {
  display: flex; align-items: center; gap: 6px;
}
.date-input {
  font-family: inherit; font-size: .75rem; padding: 5px 8px;
  border: 1px solid #ccc; background: #fff; color: #000; outline: none;
  width: 130px;
}
.date-input:focus { border-color: #000; }
.date-sep { font-size: .8rem; color: #666; }
.clear-dates {
  background: none; border: none; color: #999; cursor: pointer;
  font-size: .8rem; padding: 0 4px;
}
.clear-dates:hover { color: #000; }

/* ── Provider chips ───────────────────────────────────────────────── */
.providers-section {
  padding: 0 48px 22px;
  max-width: 900px; margin: 0 auto; width: 100%;
}
.providers-label {
  font-size: .68rem; font-weight: 700; letter-spacing: .1em;
  color: #666; margin-bottom: 9px;
  display: flex; align-items: center; gap: 10px;
}
.toggle-all-btn {
  font-family: inherit; font-size: .65rem; font-weight: 600;
  padding: 2px 8px; border: 1px solid #ccc; background: none;
  cursor: pointer; color: #666; letter-spacing: .05em;
}
.toggle-all-btn:hover { border-color: #000; color: #000; }

.provider-chips { display: flex; flex-wrap: wrap; gap: 5px; }
.chip {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 11px; font-family: inherit; font-size: .72rem;
  font-weight: 600; letter-spacing: .04em;
  border: 1px solid #ccc; background: #fff; cursor: pointer;
  transition: all .15s; color: #666;
}
.chip:hover { border-color: #000; color: #000; }
.chip--active { border-color: #000; background: #000; color: #fff; }
.chip-dot { width: 6px; height: 6px; border-radius: 50%; background: currentColor; flex-shrink: 0; }
.chip--active.chip--darkweb      { background: #1a0033; border-color: #1a0033; }
.chip--active.chip--academic     { background: #003399; border-color: #003399; }
.chip--active.chip--archive      { background: #004400; border-color: #004400; }
.chip--active.chip--social       { background: #cc3300; border-color: #cc3300; }
.chip--active.chip--alternative  { background: #550055; border-color: #550055; }
.chip--active.chip--code         { background: #004455; border-color: #004455; }
.providers-note {
  font-size: .7rem; color: #888; margin-top: 8px;
}

/* ── Results ──────────────────────────────────────────────────────── */
.results-section {
  padding: 0 48px 60px;
  max-width: 900px; margin: 0 auto; width: 100%; flex: 1;
}

.stats-bar {
  font-size: .75rem; color: #666;
  padding: 9px 0; border-top: 1px solid #eee; border-bottom: 1px solid #eee;
  margin-bottom: 14px;
  display: flex; align-items: center; flex-wrap: wrap; gap: 4px;
}
.stat-count  { font-weight: 700; color: #000; }
.stat-sep    { color: #ccc; padding: 0 2px; }
.stat-failed { color: #cc3300; }
.stat-cached { color: #006600; }
.searching-msg { font-style: italic; }
.stats-right { margin-left: auto; display: flex; gap: 8px; }
.export-btn {
  font-size: .65rem; font-weight: 700; letter-spacing: .08em;
  padding: 3px 9px; border: 1px solid #000; color: #000;
  text-decoration: none; transition: all .15s;
}
.export-btn:hover { background: #000; color: #fff; }

.type-tabs { display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 18px; }
.type-tab {
  padding: 5px 12px; font-family: inherit; font-size: .72rem;
  font-weight: 600; letter-spacing: .04em;
  border: 1px solid #ccc; background: #fff; cursor: pointer;
  color: #666; transition: all .15s;
  display: flex; align-items: center; gap: 5px;
}
.type-tab:hover  { border-color: #000; color: #000; }
.type-tab.active { background: #000; border-color: #000; color: #fff; }
.tab-count {
  font-size: .62rem; padding: 1px 5px; border-radius: 8px;
  background: rgba(255,255,255,.2);
}
.type-tab:not(.active) .tab-count { background: #eee; color: #666; }

/* Skeleton */
.skeleton-list { display: flex; flex-direction: column; gap: 14px; }
.skeleton-card {
  height: 88px;
  background: linear-gradient(90deg, #f2f2f2 25%, #e5e5e5 50%, #f2f2f2 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Result list */
.result-list { display: flex; flex-direction: column; }

/* ── Result card ──────────────────────────────────────────────────── */
.result-card { padding: 16px 0; border-bottom: 1px solid #eee; }
.result-card:last-child { border-bottom: none; }
.result-card--darkweb    { border-left: 3px solid #6600cc; padding-left: 12px; }
.result-card--academic   { border-left: 3px solid #003399; padding-left: 12px; }
.result-card--archive    { border-left: 3px solid #006600; padding-left: 12px; }
.result-card--social     { border-left: 3px solid #cc3300; padding-left: 12px; }
.result-card--alternative{ border-left: 3px solid #880088; padding-left: 12px; }
.result-card--code       { border-left: 3px solid #004455; padding-left: 12px; }

.result-meta {
  display: flex; align-items: center; flex-wrap: wrap;
  gap: 7px; margin-bottom: 5px;
}
.source-badge {
  font-size: .56rem; font-weight: 700; letter-spacing: .1em;
  padding: 2px 5px; border-radius: 2px;
}
.badge--web          { background: #000; color: #fff; }
.badge--social       { background: #cc3300; color: #fff; }
.badge--academic     { background: #003399; color: #fff; }
.badge--archive      { background: #006600; color: #fff; }
.badge--darkweb      { background: #6600cc; color: #fff; }
.badge--code         { background: #004455; color: #fff; }
.badge--encyclopedia { background: #444; color: #fff; }
.badge--alternative  { background: #880088; color: #fff; }

.source-name { font-size: .72rem; font-weight: 600; color: #444; }
.result-date, .result-author { font-size: .68rem; color: #888; }

.result-title {
  font-size: .97rem; font-weight: 600; line-height: 1.3;
  margin-bottom: 3px; display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
}
.result-title a { color: #000; text-decoration: none; }
.result-title a:hover { text-decoration: underline; text-decoration-thickness: 1px; }
.onion-tag { font-size: .65rem; background: #f0e0ff; padding: 1px 6px; border-radius: 3px; }

.result-url { font-size: .68rem; color: #1a6600; margin-bottom: 5px; word-break: break-all; }

.result-snippet {
  font-size: .83rem; color: #333; line-height: 1.55;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-actions {
  display: flex; align-items: center; flex-wrap: wrap;
  justify-content: space-between; gap: 6px; margin-top: 4px;
}
.result-extra { display: flex; flex-wrap: wrap; gap: 4px; }
.extra-pill {
  font-size: .62rem; padding: 2px 6px;
  background: #f0f0f0; color: #555; font-weight: 600; letter-spacing: .03em;
}
.extra-pill--green { background: #d4edda; color: #155724; }

.result-archive-links { display: flex; gap: 8px; flex-shrink: 0; }
.archive-link {
  font-size: .65rem; color: #888; text-decoration: none;
  padding: 2px 6px; border: 1px solid #e0e0e0;
  transition: all .15s;
}
.archive-link:hover { border-color: #000; color: #000; }

/* Empty state */
.empty-state { text-align: center; padding: 56px 0; color: #888; }
.empty-icon  { font-size: 2.5rem; margin-bottom: 10px; }

/* Load more */
.load-more-row { margin-top: 24px; display: flex; justify-content: center; }
.load-more-btn {
  font-family: inherit; font-size: .78rem; font-weight: 700;
  letter-spacing: .08em; padding: 10px 28px;
  border: 1px solid #000; background: #fff; cursor: pointer;
  transition: all .15s;
}
.load-more-btn:hover:not(:disabled) { background: #000; color: #fff; }
.load-more-btn:disabled { opacity: .4; cursor: not-allowed; }

/* Transitions */
.fade-enter-active { transition: opacity .18s, transform .18s; }
.fade-enter-from   { opacity: 0; transform: translateY(6px); }

/* ── Footer ───────────────────────────────────────────────────────── */
.search-footer {
  padding: 18px 48px; border-top: 1px solid #eee;
  font-size: .7rem; color: #888;
  display: flex; gap: 8px; align-items: center; flex-wrap: wrap;
}
.search-footer a { color: #444; text-decoration: none; }
.search-footer a:hover { color: #000; }
.sep { color: #ddd; }

/* ── History toggle button ────────────────────────────────────────────── */
.history-toggle-btn {
  background: none; border: none; padding: 0 10px;
  cursor: pointer; color: #bbb; font-size: 1.1rem; line-height: 1;
  transition: color .15s;
}
.history-toggle-btn:hover,
.history-toggle-btn.active { color: #000; }

/* ── History dropdown ─────────────────────────────────────────────────── */
.history-dropdown {
  position: absolute; top: 100%; left: 0; right: 0;
  background: #fff; border: 2px solid #000; border-top: none;
  z-index: 100;
}
.history-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 6px 14px; border-bottom: 1px solid #eee;
  font-size: .62rem; font-weight: 700; letter-spacing: .08em; color: #999;
}
.history-clear-btn {
  background: none; border: none; cursor: pointer;
  font-size: .62rem; color: #cc3300; font-family: inherit;
  font-weight: 700; letter-spacing: .05em; padding: 0;
}
.history-clear-btn:hover { text-decoration: underline; }
.history-list { list-style: none; margin: 0; padding: 0; }
.history-item {
  display: flex; align-items: center; justify-content: space-between;
  border-bottom: 1px solid #f5f5f5;
}
.history-item:last-child { border-bottom: none; }
.history-query {
  flex: 1; display: flex; align-items: center; gap: 8px;
  padding: 8px 14px; background: none; border: none;
  cursor: pointer; font-family: inherit; font-size: .84rem;
  color: #000; text-align: left;
}
.history-query:hover { background: #f8f8f8; }
.history-icon { color: #bbb; font-size: .9rem; flex-shrink: 0; }
.history-text { flex: 1; }
.history-time { font-size: .65rem; color: #aaa; flex-shrink: 0; margin-left: 6px; }
.history-remove {
  background: none; border: none; cursor: pointer;
  color: #ccc; padding: 8px 12px; font-size: .75rem;
}
.history-remove:hover { color: #cc3300; }

/* ── Action buttons ───────────────────────────────────────────────────── */
.action-btn { cursor: pointer; background: #fff; }
.action-btn--active { background: #000 !important; color: #fff !important; }
.action-btn--feed   { border-color: #ff6600 !important; color: #ff6600; }
.action-btn--feed:hover { background: #ff6600 !important; color: #fff !important; }
.action-btn--copied { background: #006600 !important; color: #fff !important; border-color: #006600 !important; }

/* ── Toast ────────────────────────────────────────────────────────────── */
.toast {
  position: fixed; bottom: 28px; left: 50%; transform: translateX(-50%);
  background: #000; color: #fff;
  padding: 9px 22px; font-size: .78rem; font-weight: 700;
  letter-spacing: .08em; z-index: 9999;
  pointer-events: none;
}
.toast-fade-enter-active, .toast-fade-leave-active { transition: opacity .25s, transform .25s; }
.toast-fade-enter-from, .toast-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(12px); }

/* ── AI Analysis panel ────────────────────────────────────────────────── */
.analysis-panel {
  border: 2px solid #000; margin-bottom: 20px;
  background: #fafafa;
}
.analysis-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 10px 16px; background: #000; color: #fff;
}
.analysis-title { font-size: .72rem; font-weight: 700; letter-spacing: .12em; }
.analysis-close {
  background: none; border: none; color: #fff; cursor: pointer;
  font-size: .9rem; padding: 0; line-height: 1;
}
.analysis-close:hover { opacity: .7; }
.analysis-loading {
  padding: 20px 16px; font-size: .82rem; color: #666;
  display: flex; align-items: center; gap: 8px;
}
.analysis-error {
  padding: 14px 16px; font-size: .78rem; color: #cc3300;
  background: #fff5f5; border-top: 1px solid #ffcccc;
}
.analysis-body { padding: 4px 0; }
.analysis-section {
  padding: 12px 16px; border-bottom: 1px solid #eee;
}
.analysis-section:last-child { border-bottom: none; }
.analysis-label {
  font-size: .58rem; font-weight: 700; letter-spacing: .12em;
  color: #888; margin-bottom: 6px;
}
.analysis-text { font-size: .84rem; color: #222; line-height: 1.55; margin: 0; }
.analysis-text--highlight {
  background: #fffbe6; border-left: 3px solid #ff6600;
  padding: 8px 12px;
}
.analysis-list {
  margin: 0; padding-left: 18px;
  font-size: .82rem; color: #333; line-height: 1.7;
}
.analysis-list--warn { color: #883300; }
.further-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.further-tag {
  font-family: inherit; font-size: .72rem; font-weight: 600;
  padding: 4px 10px; border: 1px solid #ccc; background: #fff;
  cursor: pointer; color: #333; transition: all .15s;
}
.further-tag:hover { border-color: #000; background: #000; color: #fff; }

/* Slide transition for analysis panel */
.slide-down-enter-active { transition: opacity .25s; }
.slide-down-leave-active { transition: opacity .2s; }
.slide-down-enter-from, .slide-down-leave-to { opacity: 0; }

/* ── Compact result card ──────────────────────────────────────────────── */
.result-card--compact { padding: 8px 0; }
.result-card--compact .result-snippet {
  -webkit-line-clamp: 2;
  margin-bottom: 4px;
}
.result-card--compact .result-actions { margin-top: 2px; }

/* ── Responsive ───────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .navbar, .hero, .providers-section, .results-section, .search-footer {
    padding-left: 16px; padding-right: 16px;
  }
  .hero-title { font-size: 1.7rem; }
  .search-btn { padding: 13px 14px; font-size: .68rem; }
  .date-input { width: 110px; }
  .nav-hint   { display: none; }
  .options-row { gap: 12px; }
}
</style>
