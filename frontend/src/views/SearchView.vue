<template>
  <div class="search-root">

    <!-- ── NAV ─────────────────────────────────────────────── -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand">MIROFISH</router-link>
      <div class="nav-links">
        <span class="nav-tag">DEEP SEARCH</span>
      </div>
    </nav>

    <!-- ── HERO / SEARCH BAR ─────────────────────────────── -->
    <section class="hero">
      <div class="hero-heading">
        <span class="pill">AD-FREE</span>
        <span class="pill pill--dark">UNCENSORED</span>
        <span class="pill pill--accent">UNFILTERED</span>
      </div>
      <h1 class="hero-title">Search Without Walls</h1>
      <p class="hero-sub">
        Aggregates {{ providerCount }}+ sources: web, social, academic, archived,
        dark-web index — none of which Google shows you.
      </p>

      <!-- Search form -->
      <form class="search-form" @submit.prevent="runSearch">
        <div class="search-input-wrap">
          <input
            ref="inputRef"
            v-model="query"
            class="search-input"
            placeholder="Search anything…"
            autocomplete="off"
            spellcheck="false"
            @input="onInputChange"
            @keydown.down.prevent="moveSuggestion(1)"
            @keydown.up.prevent="moveSuggestion(-1)"
            @keydown.escape="clearSuggestions"
          />
          <button type="submit" class="search-btn" :disabled="searching || !query.trim()">
            <span v-if="!searching">SEARCH</span>
            <span v-else class="spin">◌</span>
          </button>
        </div>

        <!-- Autocomplete dropdown -->
        <ul v-if="suggestions.length" class="suggestions">
          <li
            v-for="(s, i) in suggestions"
            :key="i"
            :class="{ active: i === suggestionIdx }"
            @mousedown.prevent="acceptSuggestion(s)"
          >{{ s }}</li>
        </ul>
      </form>

      <!-- Mode toggle -->
      <div class="mode-row">
        <label class="mode-toggle">
          <input type="checkbox" v-model="deepMode" />
          <span class="toggle-track"><span class="toggle-thumb" /></span>
          <span class="mode-label">
            Deep mode
            <span class="mode-hint">(+ dark web index, academic, GitHub)</span>
          </span>
        </label>
      </div>
    </section>

    <!-- ── PROVIDER CHIPS ────────────────────────────────── -->
    <section v-if="availableProviders.length" class="providers-section">
      <div class="providers-label">Sources</div>
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
        >
          <span class="chip-dot" />{{ p.name }}
        </button>
      </div>
      <div class="providers-note">
        <span v-if="unavailableProviders.length">
          {{ unavailableProviders.map(p => p.name).join(', ') }}
          require API keys (see .env).
        </span>
      </div>
    </section>

    <!-- ── RESULTS ───────────────────────────────────────── -->
    <section v-if="hasSearched" class="results-section">

      <!-- Stats bar -->
      <div class="stats-bar">
        <template v-if="!searching">
          <span class="stat-count">{{ results.length }} results</span>
          <span class="stat-sep">·</span>
          <span class="stat-time">{{ tookMs }}ms</span>
          <span class="stat-sep">·</span>
          <span class="stat-sources">
            from {{ usedProviders.join(', ') || 'no sources' }}
          </span>
          <span v-if="failedProviders.length" class="stat-failed">
            · {{ failedProviders.length }} failed
          </span>
        </template>
        <template v-else>
          <span class="searching-msg">Searching {{ pendingCount }} source{{ pendingCount !== 1 ? 's' : '' }}…</span>
        </template>
      </div>

      <!-- Type filter tabs -->
      <div class="type-tabs">
        <button
          v-for="tab in typeTabs"
          :key="tab.value"
          class="type-tab"
          :class="{ active: activeTab === tab.value }"
          @click="activeTab = tab.value"
        >
          {{ tab.label }}
          <span class="tab-count">{{ tab.count }}</span>
        </button>
      </div>

      <!-- Loading skeleton -->
      <div v-if="searching" class="skeleton-list">
        <div v-for="i in 6" :key="i" class="skeleton-card" />
      </div>

      <!-- Result cards -->
      <transition-group v-else name="fade" tag="div" class="result-list">
        <article
          v-for="(r, idx) in filteredResults"
          :key="r.url + idx"
          class="result-card"
          :class="`result-card--${r.source_type}`"
        >
          <div class="result-meta">
            <span class="source-badge" :class="`badge--${r.source_type}`">
              {{ sourceLabel(r.source_type) }}
            </span>
            <span class="source-name">{{ r.source }}</span>
            <span v-if="r.published_at" class="result-date">
              {{ formatDate(r.published_at) }}
            </span>
            <span v-if="r.author" class="result-author">by {{ r.author }}</span>
          </div>

          <h3 class="result-title">
            <a :href="r.url" target="_blank" rel="noopener noreferrer">
              {{ r.title || r.url }}
            </a>
            <span v-if="r.source_type === 'darkweb'" class="onion-badge" title="Tor .onion address">🧅</span>
          </h3>

          <div class="result-url">{{ truncateUrl(r.url) }}</div>

          <p v-if="r.snippet" class="result-snippet">{{ r.snippet }}</p>

          <!-- Extra metadata pills -->
          <div class="result-extra" v-if="hasExtras(r)">
            <span v-if="r.extra.stars" class="extra-pill">★ {{ r.extra.stars }}</span>
            <span v-if="r.extra.score" class="extra-pill">↑ {{ r.extra.score }}</span>
            <span v-if="r.extra.num_comments" class="extra-pill">💬 {{ r.extra.num_comments }}</span>
            <span v-if="r.extra.subreddit" class="extra-pill">{{ r.extra.subreddit }}</span>
            <span v-if="r.extra.categories && r.extra.categories.length" class="extra-pill">
              {{ r.extra.categories.slice(0, 2).join(' · ') }}
            </span>
            <span v-if="r.extra.open_access" class="extra-pill extra-pill--green">Open Access</span>
            <span v-if="r.extra.doi" class="extra-pill">DOI</span>
            <span v-if="r.source_type === 'darkweb'" class="extra-pill extra-pill--dark">
              {{ r.extra.note ? 'Requires Tor' : 'Tor' }}
            </span>
          </div>
        </article>
      </transition-group>

      <!-- Empty state -->
      <div v-if="!searching && filteredResults.length === 0" class="empty-state">
        <div class="empty-icon">∅</div>
        <p v-if="results.length === 0">No results found. Try different keywords or enable more sources.</p>
        <p v-else>No results in this category. Switch tabs to see results from other source types.</p>
      </div>

    </section>

    <!-- ── FOOTER ─────────────────────────────────────────── -->
    <footer class="search-footer">
      <span>MiroFish Deep Search</span>
      <span class="sep">·</span>
      <span>No ads. No tracking. No filter bubbles.</span>
      <span class="sep">·</span>
      <a href="https://github.com/666ghj/MiroFish" target="_blank">GitHub ↗</a>
    </footer>

  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { getProviders, search as apiSearch, suggest as apiSuggest } from '../api/search'

// ── State ───────────────────────────────────────────────────────────────────

const query         = ref('')
const searching     = ref(false)
const hasSearched   = ref(false)
const results       = ref([])
const usedProviders = ref([])
const failedProviders = ref([])
const tookMs        = ref(0)
const deepMode      = ref(false)
const activeTab     = ref('all')

const suggestions     = ref([])
const suggestionIdx   = ref(-1)
const suggestTimeout  = ref(null)

const availableProviders   = ref([])
const unavailableProviders = ref([])
const selectedProviders    = ref([])

const inputRef = ref(null)

// ── Provider loading ─────────────────────────────────────────────────────────

onMounted(async () => {
  try {
    const data = await getProviders()
    const all = data.providers || []
    availableProviders.value   = all.filter(p => p.available)
    unavailableProviders.value = all.filter(p => !p.available)
    // Default: select all available providers
    selectedProviders.value = availableProviders.value.map(p => p.id)
  } catch (e) {
    console.warn('Could not load providers:', e)
  }
  inputRef.value?.focus()
})

// When deep mode toggles, update selected providers to match
watch(deepMode, () => {
  // Already handled by the 'providers' param we send to API
})

// ── Computed ─────────────────────────────────────────────────────────────────

const providerCount = computed(() => availableProviders.value.length || 11)
const pendingCount  = computed(() => selectedProviders.value.length)

const typeTabs = computed(() => {
  const counts = {}
  for (const r of results.value) {
    counts[r.source_type] = (counts[r.source_type] || 0) + 1
  }
  const tabs = [{ label: 'All', value: 'all', count: results.value.length }]
  const labels = {
    web: 'Web', social: 'Social', academic: 'Academic',
    archive: 'Archive', darkweb: 'Dark Web', code: 'Code',
    encyclopedia: 'Wiki', alternative: 'Alternative',
  }
  for (const [type, label] of Object.entries(labels)) {
    if (counts[type]) {
      tabs.push({ label, value: type, count: counts[type] })
    }
  }
  return tabs
})

const filteredResults = computed(() => {
  if (activeTab.value === 'all') return results.value
  return results.value.filter(r => r.source_type === activeTab.value)
})

// ── Search ───────────────────────────────────────────────────────────────────

async function runSearch() {
  const q = query.value.trim()
  if (!q || searching.value) return

  clearSuggestions()
  searching.value = true
  hasSearched.value = true
  activeTab.value = 'all'

  try {
    const providers = selectedProviders.value.length
      ? selectedProviders.value
      : null

    const data = await apiSearch({
      query: q,
      providers,
      maxPerProvider: 12,
      mode: deepMode.value ? 'deep' : 'default',
    })

    results.value       = data.results || []
    usedProviders.value = data.providers_used || []
    failedProviders.value = data.providers_failed || []
    tookMs.value        = data.took_ms || 0
  } catch (err) {
    console.error('Search error:', err)
    results.value = []
  } finally {
    searching.value = false
  }
}

// ── Autocomplete ─────────────────────────────────────────────────────────────

function onInputChange() {
  suggestionIdx.value = -1
  clearTimeout(suggestTimeout.value)
  if (query.value.length < 2) {
    suggestions.value = []
    return
  }
  suggestTimeout.value = setTimeout(async () => {
    suggestions.value = await apiSuggest(query.value)
  }, 250)
}

function moveSuggestion(dir) {
  if (!suggestions.value.length) return
  suggestionIdx.value = Math.max(
    -1,
    Math.min(suggestions.value.length - 1, suggestionIdx.value + dir)
  )
  if (suggestionIdx.value >= 0) {
    query.value = suggestions.value[suggestionIdx.value]
  }
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

// ── Provider toggle ───────────────────────────────────────────────────────────

function toggleProvider(id) {
  const idx = selectedProviders.value.indexOf(id)
  if (idx === -1) {
    selectedProviders.value.push(id)
  } else {
    if (selectedProviders.value.length === 1) return // keep at least one
    selectedProviders.value.splice(idx, 1)
  }
}

// ── Display helpers ───────────────────────────────────────────────────────────

function sourceLabel(type) {
  return {
    web: 'WEB', social: 'SOCIAL', academic: 'ACADEMIC',
    archive: 'ARCHIVE', darkweb: 'DARK WEB', code: 'CODE',
    encyclopedia: 'WIKI', alternative: 'ALT',
  }[type] || type.toUpperCase()
}

function truncateUrl(url) {
  try {
    const u = new URL(url)
    const path = u.pathname + u.search
    const base = u.hostname.replace(/^www\./, '')
    return base + (path.length > 50 ? path.slice(0, 50) + '…' : path)
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
  } catch {
    return dateStr.slice(0, 10)
  }
}

function hasExtras(r) {
  const e = r.extra || {}
  return e.stars || e.score || e.num_comments || e.subreddit ||
    (e.categories && e.categories.length) || e.open_access || e.doi ||
    r.source_type === 'darkweb'
}
</script>

<style scoped>
/* ── Root & Layout ───────────────────────────────────────────────────── */
.search-root {
  min-height: 100vh;
  background: #ffffff;
  color: #000000;
  font-family: 'JetBrains Mono', 'Space Grotesk', monospace;
  display: flex;
  flex-direction: column;
}

/* ── Navbar ─────────────────────────────────────────────────────────── */
.navbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 48px;
  border-bottom: 1px solid #000;
}
.nav-brand {
  font-size: 1.1rem;
  font-weight: 700;
  letter-spacing: 0.15em;
  color: #000;
  text-decoration: none;
}
.nav-brand:hover { opacity: 0.7; }
.nav-tag {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: 4px 10px;
  border: 1px solid #000;
}

/* ── Hero ───────────────────────────────────────────────────────────── */
.hero {
  padding: 56px 48px 40px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
}
.hero-heading {
  display: flex;
  gap: 8px;
  margin-bottom: 18px;
  flex-wrap: wrap;
}
.pill {
  font-size: 0.65rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  padding: 4px 10px;
  border: 1px solid #000;
}
.pill--dark  { background: #000; color: #fff; }
.pill--accent{ background: #ff6600; color: #fff; border-color: #ff6600; }

.hero-title {
  font-size: clamp(2rem, 5vw, 3.2rem);
  font-weight: 800;
  line-height: 1.1;
  margin-bottom: 14px;
  letter-spacing: -0.02em;
}
.hero-sub {
  font-size: 0.95rem;
  color: #444;
  margin-bottom: 32px;
  line-height: 1.5;
}

/* ── Search Form ─────────────────────────────────────────────────────── */
.search-form {
  position: relative;
  margin-bottom: 20px;
}
.search-input-wrap {
  display: flex;
  border: 2px solid #000;
}
.search-input {
  flex: 1;
  padding: 14px 18px;
  font-size: 1rem;
  font-family: inherit;
  border: none;
  outline: none;
  background: transparent;
  color: #000;
}
.search-input::placeholder { color: #888; }
.search-btn {
  padding: 14px 28px;
  background: #000;
  color: #fff;
  border: none;
  font-family: inherit;
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  cursor: pointer;
  transition: background 0.15s;
}
.search-btn:hover:not(:disabled) { background: #333; }
.search-btn:disabled { opacity: 0.4; cursor: not-allowed; }
.spin {
  display: inline-block;
  animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

/* ── Suggestions ─────────────────────────────────────────────────────── */
.suggestions {
  position: absolute;
  top: 100%;
  left: 0; right: 0;
  background: #fff;
  border: 2px solid #000;
  border-top: none;
  list-style: none;
  z-index: 100;
  margin: 0; padding: 0;
}
.suggestions li {
  padding: 10px 18px;
  cursor: pointer;
  font-size: 0.9rem;
}
.suggestions li:hover,
.suggestions li.active { background: #f0f0f0; }

/* ── Mode toggle ─────────────────────────────────────────────────────── */
.mode-row { display: flex; align-items: center; gap: 12px; }
.mode-toggle {
  display: flex;
  align-items: center;
  gap: 10px;
  cursor: pointer;
  user-select: none;
}
.mode-toggle input { display: none; }
.toggle-track {
  width: 38px; height: 22px;
  background: #ccc;
  border-radius: 11px;
  position: relative;
  transition: background 0.2s;
}
.mode-toggle input:checked + .toggle-track { background: #000; }
.toggle-thumb {
  position: absolute;
  top: 3px; left: 3px;
  width: 16px; height: 16px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}
.mode-toggle input:checked + .toggle-track .toggle-thumb { transform: translateX(16px); }
.mode-label {
  font-size: 0.85rem;
  font-weight: 600;
}
.mode-hint {
  font-weight: 400;
  color: #666;
  font-size: 0.78rem;
}

/* ── Provider chips ─────────────────────────────────────────────────── */
.providers-section {
  padding: 0 48px 24px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
}
.providers-label {
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  margin-bottom: 10px;
  color: #666;
}
.provider-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  border: 1px solid #ccc;
  background: #fff;
  cursor: pointer;
  transition: all 0.15s;
  color: #666;
}
.chip:hover { border-color: #000; color: #000; }
.chip--active { border-color: #000; background: #000; color: #fff; }
.chip-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}
/* Type-specific active colours */
.chip--active.chip--darkweb  { background: #1a0033; border-color: #1a0033; }
.chip--active.chip--academic { background: #003366; border-color: #003366; }
.chip--active.chip--archive  { background: #004400; border-color: #004400; }
.chip--active.chip--social   { background: #cc4400; border-color: #cc4400; }
.chip--active.chip--alternative { background: #550055; border-color: #550055; }
.providers-note {
  font-size: 0.72rem;
  color: #888;
  margin-top: 8px;
}

/* ── Results section ─────────────────────────────────────────────────── */
.results-section {
  padding: 0 48px 60px;
  max-width: 860px;
  margin: 0 auto;
  width: 100%;
  flex: 1;
}

/* Stats bar */
.stats-bar {
  font-size: 0.78rem;
  color: #666;
  margin-bottom: 16px;
  padding: 10px 0;
  border-top: 1px solid #eee;
  border-bottom: 1px solid #eee;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}
.stat-count { font-weight: 700; color: #000; }
.stat-sep   { color: #ccc; padding: 0 2px; }
.stat-failed{ color: #cc4400; }
.searching-msg { font-style: italic; }

/* Type tabs */
.type-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-bottom: 20px;
}
.type-tab {
  padding: 6px 14px;
  font-family: inherit;
  font-size: 0.75rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  border: 1px solid #ccc;
  background: #fff;
  cursor: pointer;
  color: #666;
  transition: all 0.15s;
  display: flex;
  align-items: center;
  gap: 6px;
}
.type-tab:hover  { border-color: #000; color: #000; }
.type-tab.active { background: #000; border-color: #000; color: #fff; }
.tab-count {
  font-size: 0.65rem;
  padding: 1px 5px;
  background: rgba(255,255,255,0.2);
  border-radius: 10px;
}
.type-tab:not(.active) .tab-count { background: #eee; color: #666; }

/* Skeleton loader */
.skeleton-list { display: flex; flex-direction: column; gap: 16px; }
.skeleton-card {
  height: 90px;
  background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
  background-size: 200% 100%;
  animation: shimmer 1.4s infinite;
  border-left: 3px solid #e0e0e0;
}
@keyframes shimmer {
  0%   { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

/* Result list */
.result-list { display: flex; flex-direction: column; gap: 0; }

/* ── Result Card ─────────────────────────────────────────────────────── */
.result-card {
  padding: 18px 0;
  border-bottom: 1px solid #eee;
}
.result-card:last-child { border-bottom: none; }
.result-card--darkweb   { border-left: 3px solid #6600cc; padding-left: 14px; }
.result-card--academic  { border-left: 3px solid #0044cc; padding-left: 14px; }
.result-card--archive   { border-left: 3px solid #006600; padding-left: 14px; }
.result-card--social    { border-left: 3px solid #cc4400; padding-left: 14px; }
.result-card--alternative { border-left: 3px solid #880088; padding-left: 14px; }
.result-card--code      { border-left: 3px solid #005566; padding-left: 14px; }

.result-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.source-badge {
  font-size: 0.58rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  padding: 2px 6px;
  border-radius: 2px;
}
.badge--web          { background: #000; color: #fff; }
.badge--social       { background: #cc4400; color: #fff; }
.badge--academic     { background: #0044cc; color: #fff; }
.badge--archive      { background: #006600; color: #fff; }
.badge--darkweb      { background: #6600cc; color: #fff; }
.badge--code         { background: #005566; color: #fff; }
.badge--encyclopedia { background: #444; color: #fff; }
.badge--alternative  { background: #880088; color: #fff; }

.source-name {
  font-size: 0.75rem;
  font-weight: 600;
  color: #444;
}
.result-date, .result-author {
  font-size: 0.72rem;
  color: #888;
}

.result-title {
  font-size: 1rem;
  font-weight: 600;
  line-height: 1.3;
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
}
.result-title a {
  color: #000;
  text-decoration: none;
}
.result-title a:hover {
  text-decoration: underline;
  text-decoration-thickness: 1px;
}
.onion-badge { font-size: 0.8rem; }

.result-url {
  font-size: 0.72rem;
  color: #006600;
  margin-bottom: 6px;
  font-family: inherit;
  word-break: break-all;
}

.result-snippet {
  font-size: 0.85rem;
  color: #333;
  line-height: 1.5;
  margin-bottom: 6px;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.result-extra {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
.extra-pill {
  font-size: 0.65rem;
  padding: 2px 7px;
  background: #f0f0f0;
  color: #555;
  font-weight: 600;
  letter-spacing: 0.04em;
}
.extra-pill--green { background: #d4edda; color: #155724; }
.extra-pill--dark  { background: #e8d5ff; color: #440088; }

/* ── Empty / transition ──────────────────────────────────────────────── */
.empty-state {
  text-align: center;
  padding: 60px 0;
  color: #888;
}
.empty-icon {
  font-size: 3rem;
  margin-bottom: 12px;
}

.fade-enter-active { transition: opacity 0.2s, transform 0.2s; }
.fade-enter-from   { opacity: 0; transform: translateY(8px); }

/* ── Footer ─────────────────────────────────────────────────────────── */
.search-footer {
  padding: 20px 48px;
  border-top: 1px solid #eee;
  font-size: 0.72rem;
  color: #888;
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.search-footer a { color: #444; text-decoration: none; }
.search-footer a:hover { color: #000; }
.sep { color: #ccc; }

/* ── Responsive ─────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .navbar,
  .hero,
  .providers-section,
  .results-section,
  .search-footer { padding-left: 20px; padding-right: 20px; }
  .hero-title { font-size: 1.8rem; }
  .search-btn { padding: 14px 16px; font-size: 0.7rem; }
  .type-tabs  { gap: 3px; }
  .type-tab   { padding: 5px 10px; }
}
</style>
