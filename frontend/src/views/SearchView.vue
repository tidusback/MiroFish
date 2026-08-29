<template>
  <div class="search-root">
    <!-- Navbar -->
    <nav class="navbar">
      <router-link to="/" class="nav-brand">MIROFISH</router-link>
      <div class="nav-links">
        <span class="nav-tag">OPEN SEARCH</span>
        <a href="https://github.com/666ghj/MiroFish" target="_blank" class="github-link">
          GitHub <span class="arrow">↗</span>
        </a>
      </div>
    </nav>

    <!-- Hero / search bar area -->
    <div class="search-hero" :class="{ 'compact': hasResults }">
      <div v-if="!hasResults" class="hero-headline">
        <div class="headline-tag">UNCENSORED · NO ADS · NO FILTER BUBBLES</div>
        <h1 class="hero-title">Search<br><span class="orange-text">Everything</span></h1>
        <p class="hero-sub">
          Aggregates DuckDuckGo, Reddit, Internet Archive, arXiv, Ahmia (Tor index),
          GitHub and more — surfacing what mainstream engines bury or delete.
        </p>
      </div>

      <div class="search-bar-wrap">
        <div class="search-bar" :class="{ focused: inputFocused }">
          <span class="search-icon">⌕</span>
          <input
            ref="inputRef"
            v-model="query"
            class="search-input"
            type="text"
            placeholder="Search anything — unrestricted…"
            @keydown.enter="runSearch"
            @focus="inputFocused = true"
            @blur="inputFocused = false"
            autocomplete="off"
          />
          <button
            v-if="query"
            class="clear-btn"
            @click="query = ''; hasResults = false; results = []"
          >×</button>
        </div>

        <!-- Engine selector chips -->
        <div class="engine-chips">
          <button
            class="chip"
            :class="{ active: selectedEngines.length === 0 }"
            @click="selectedEngines = []"
          >All Engines</button>
          <button
            v-for="eng in allEngines"
            :key="eng.id"
            class="chip"
            :class="[{ active: selectedEngines.includes(eng.id) }, `cat-${eng.category}`]"
            :title="eng.description"
            @click="toggleEngine(eng.id)"
          >
            <span class="chip-dot" :class="`dot-${eng.category}`"></span>
            {{ eng.name }}
          </button>
        </div>

        <div class="search-actions">
          <button class="search-btn" :disabled="!query.trim() || loading" @click="runSearch">
            <span v-if="!loading">SEARCH →</span>
            <span v-else class="loading-dots">Searching<span class="dots">...</span></span>
          </button>
          <button class="deep-btn" :disabled="!query.trim() || loading" @click="runDeepSearch" title="Runs every available engine including Tor index and Archive.org">
            DEEP SEARCH ⬛
          </button>
        </div>
      </div>

      <!-- Error -->
      <div v-if="error" class="error-bar">
        <span class="err-icon">⚠</span> {{ error }}
      </div>
    </div>

    <!-- Results area -->
    <div v-if="hasResults" class="results-area">
      <!-- Stats bar -->
      <div class="stats-bar">
        <span class="stat-query">Results for <strong>{{ lastQuery }}</strong></span>
        <span class="stat-divider">·</span>
        <span class="stat-count">{{ results.length }} results</span>
        <span class="stat-divider">·</span>
        <span class="stat-engines">
          Engines: {{ enginesUsed.join(', ') || '—' }}
        </span>
        <span v-if="enginesFailed.length" class="stat-failed">
          · {{ enginesFailed.length }} failed
        </span>
      </div>

      <!-- Filter tabs -->
      <div class="filter-tabs">
        <button
          v-for="cat in activeCategories"
          :key="cat"
          class="filter-tab"
          :class="{ active: activeFilter === cat }"
          @click="activeFilter = cat"
        >{{ catLabel(cat) }} ({{ countByCategory(cat) }})</button>
      </div>

      <!-- Result cards -->
      <div class="result-list">
        <div
          v-for="res in filteredResults"
          :key="res.url"
          class="result-card"
        >
          <div class="result-meta">
            <span class="engine-badge" :class="`badge-${res.source_engine}`">
              {{ res.source_label || res.source_engine }}
            </span>
            <span v-if="res.published" class="result-date">{{ formatDate(res.published) }}</span>
            <span v-if="res.extra && res.extra.stars !== undefined" class="result-extra">
              ★ {{ res.extra.stars }}
            </span>
            <span v-if="res.extra && res.extra.score !== undefined" class="result-extra">
              ↑ {{ res.extra.score }}
            </span>
          </div>

          <a :href="res.url" target="_blank" rel="noopener noreferrer" class="result-title">
            {{ res.title || res.url }}
          </a>

          <div class="result-url">{{ truncateUrl(res.url) }}</div>

          <p class="result-snippet" v-if="res.snippet">{{ res.snippet }}</p>

          <div class="result-actions">
            <a :href="res.url" target="_blank" rel="noopener noreferrer" class="action-link">
              Open ↗
            </a>
            <a
              :href="`https://web.archive.org/web/*/${res.url}`"
              target="_blank"
              rel="noopener noreferrer"
              class="action-link archive-link"
              title="Search Wayback Machine for archived versions"
            >
              Archive ⟳
            </a>
            <button
              class="action-link fetch-link"
              @click="fetchArticle(res)"
              :disabled="fetchingUrl === res.url"
              title="Fetch full article text"
            >
              {{ fetchingUrl === res.url ? 'Fetching…' : 'Full Text ⤓' }}
            </button>
          </div>

          <!-- Expanded full text -->
          <div v-if="expandedArticles[res.url]" class="article-body">
            <div class="article-body-header">Full extracted text:</div>
            <pre class="article-text">{{ expandedArticles[res.url] }}</pre>
          </div>
        </div>

        <div v-if="filteredResults.length === 0 && !loading" class="no-results">
          No results for this filter. Try a different category tab or engine.
        </div>
      </div>
    </div>

    <!-- Engines info panel (shown before first search) -->
    <div v-if="!hasResults && allEngines.length > 0" class="engines-panel">
      <div class="engines-header">
        <span class="diamond">◇</span> AVAILABLE DATA SOURCES
      </div>
      <div class="engines-grid">
        <div
          v-for="eng in allEngines"
          :key="eng.id"
          class="engine-card"
          :class="`cat-bg-${eng.category}`"
        >
          <div class="engine-name">{{ eng.name }}</div>
          <div class="engine-cat">{{ catLabel(eng.category) }}</div>
          <div class="engine-desc">{{ eng.description }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { searchQuery, searchDeep, listEngines, fetchArticleApi } from '../api/search.js'

const query = ref('')
const loading = ref(false)
const error = ref('')
const results = ref([])
const hasResults = ref(false)
const lastQuery = ref('')
const enginesUsed = ref([])
const enginesFailed = ref([])
const inputFocused = ref(false)
const inputRef = ref(null)
const allEngines = ref([])
const selectedEngines = ref([])
const activeFilter = ref('all')
const expandedArticles = ref({})
const fetchingUrl = ref(null)

onMounted(async () => {
  try {
    const data = await listEngines()
    allEngines.value = data.engines || []
  } catch {
    // not fatal
  }
  inputRef.value?.focus()
})

function toggleEngine(id) {
  const i = selectedEngines.value.indexOf(id)
  if (i === -1) selectedEngines.value.push(id)
  else selectedEngines.value.splice(i, 1)
}

async function runSearch() {
  const q = query.value.trim()
  if (!q || loading.value) return
  await doSearch(q, false)
}

async function runDeepSearch() {
  const q = query.value.trim()
  if (!q || loading.value) return
  await doSearch(q, true)
}

async function doSearch(q, deep) {
  loading.value = true
  error.value = ''
  hasResults.value = false
  expandedArticles.value = {}
  activeFilter.value = 'all'

  try {
    let data
    if (deep) {
      data = await searchDeep(q)
    } else {
      data = await searchQuery(q, selectedEngines.value.length ? selectedEngines.value : null)
    }
    results.value = data.results || []
    enginesUsed.value = data.engines_used || []
    enginesFailed.value = data.engines_failed || []
    lastQuery.value = q
    hasResults.value = true
  } catch (err) {
    error.value = err.message || 'Search failed. Check the backend is running.'
  } finally {
    loading.value = false
  }
}

async function fetchArticle(res) {
  fetchingUrl.value = res.url
  try {
    const data = await fetchArticleApi(res.url)
    expandedArticles.value[res.url] = data.content || '(no content extracted)'
  } catch {
    expandedArticles.value[res.url] = '(fetch failed)'
  } finally {
    fetchingUrl.value = null
  }
}

// Filtering

const activeCategories = computed(() => {
  const cats = new Set(['all'])
  results.value.forEach(r => {
    const eng = allEngines.value.find(e => e.id === r.source_engine)
    if (eng) cats.add(eng.category)
    else cats.add('general')
  })
  return [...cats]
})

const filteredResults = computed(() => {
  if (activeFilter.value === 'all') return results.value
  return results.value.filter(r => {
    const eng = allEngines.value.find(e => e.id === r.source_engine)
    return (eng ? eng.category : 'general') === activeFilter.value
  })
})

function countByCategory(cat) {
  if (cat === 'all') return results.value.length
  return results.value.filter(r => {
    const eng = allEngines.value.find(e => e.id === r.source_engine)
    return (eng ? eng.category : 'general') === cat
  }).length
}

function catLabel(cat) {
  const labels = {
    all: 'All', general: 'General', social: 'Social',
    academic: 'Academic', deep: 'Deep Web', technical: 'Technical',
  }
  return labels[cat] || cat
}

function truncateUrl(url) {
  try {
    const u = new URL(url)
    const path = u.pathname.length > 40 ? u.pathname.slice(0, 40) + '…' : u.pathname
    return u.hostname + path
  } catch {
    return url.slice(0, 60)
  }
}

function formatDate(d) {
  if (!d) return ''
  const s = String(d)
  if (s.length >= 10) return s.slice(0, 10)
  return s
}
</script>

<style scoped>
/* ── Variables ─────────────────────────────────────────────────────────── */
:root {
  --black: #000;
  --white: #fff;
  --orange: #ff4500;
  --border: #e5e5e5;
  --font-mono: 'JetBrains Mono', monospace;
}

/* ── Layout ────────────────────────────────────────────────────────────── */
.search-root {
  min-height: 100vh;
  background: #fff;
  font-family: 'Space Grotesk', 'Noto Sans SC', system-ui, sans-serif;
  color: #000;
}

/* ── Navbar ────────────────────────────────────────────────────────────── */
.navbar {
  height: 60px;
  background: #000;
  color: #fff;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 40px;
}

.nav-brand {
  font-family: var(--font-mono);
  font-weight: 800;
  letter-spacing: 1px;
  font-size: 1.2rem;
  color: #fff;
  text-decoration: none;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 20px;
}

.nav-tag {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #ff4500;
  letter-spacing: 1px;
  font-weight: 700;
  border: 1px solid #ff4500;
  padding: 3px 8px;
}

.github-link {
  color: #fff;
  text-decoration: none;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  opacity: 0.7;
}
.github-link:hover { opacity: 1; }

/* ── Hero ──────────────────────────────────────────────────────────────── */
.search-hero {
  max-width: 860px;
  margin: 0 auto;
  padding: 80px 24px 40px;
  transition: padding 0.3s;
}

.search-hero.compact {
  padding: 24px 24px 20px;
}

.headline-tag {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #ff4500;
  letter-spacing: 2px;
  font-weight: 700;
  margin-bottom: 20px;
}

.hero-title {
  font-size: 4rem;
  font-weight: 500;
  line-height: 1.15;
  margin: 0 0 24px;
  letter-spacing: -2px;
}

.orange-text {
  color: #ff4500;
}

.hero-sub {
  font-size: 1rem;
  color: #555;
  line-height: 1.7;
  max-width: 640px;
  margin-bottom: 40px;
}

/* ── Search bar ────────────────────────────────────────────────────────── */
.search-bar-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.search-bar {
  display: flex;
  align-items: center;
  border: 2px solid #ccc;
  background: #fafafa;
  transition: border-color 0.2s;
}

.search-bar.focused {
  border-color: #000;
  background: #fff;
}

.search-icon {
  padding: 0 14px;
  font-size: 1.4rem;
  color: #aaa;
  user-select: none;
}

.search-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: 16px 0;
  font-size: 1.1rem;
  font-family: inherit;
  outline: none;
  color: #000;
}

.search-input::placeholder { color: #bbb; }

.clear-btn {
  padding: 0 16px;
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.4rem;
  color: #999;
  line-height: 1;
}

/* ── Engine chips ──────────────────────────────────────────────────────── */
.engine-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.chip {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border: 1px solid #ddd;
  background: #fff;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  cursor: pointer;
  color: #555;
  border-radius: 2px;
  transition: all 0.15s;
}

.chip:hover { border-color: #999; color: #000; }
.chip.active { background: #000; color: #fff; border-color: #000; }

.chip-dot {
  width: 6px; height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.dot-general  { background: #555; }
.dot-social   { background: #e67e22; }
.dot-academic { background: #2980b9; }
.dot-deep     { background: #8e44ad; }
.dot-technical { background: #27ae60; }

/* ── Action buttons ────────────────────────────────────────────────────── */
.search-actions {
  display: flex;
  gap: 10px;
}

.search-btn {
  flex: 1;
  background: #000;
  color: #fff;
  border: none;
  padding: 16px;
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 1px;
  cursor: pointer;
  transition: background 0.2s;
}

.search-btn:hover:not(:disabled) { background: #ff4500; }
.search-btn:disabled { background: #ccc; cursor: not-allowed; }

.deep-btn {
  background: #1a1a1a;
  color: #fff;
  border: 1px solid #444;
  padding: 16px 20px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.deep-btn:hover:not(:disabled) { background: #8e44ad; border-color: #8e44ad; }
.deep-btn:disabled { background: #ccc; border-color: #ccc; cursor: not-allowed; }

.loading-dots .dots {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* ── Error ─────────────────────────────────────────────────────────────── */
.error-bar {
  background: #fff0f0;
  border: 1px solid #ffcccc;
  color: #cc0000;
  padding: 12px 16px;
  font-family: var(--font-mono);
  font-size: 0.85rem;
  margin-top: 12px;
}

/* ── Results area ──────────────────────────────────────────────────────── */
.results-area {
  max-width: 860px;
  margin: 0 auto;
  padding: 0 24px 60px;
}

.stats-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: #888;
  padding: 12px 0 16px;
  border-bottom: 1px solid #eee;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.stat-query strong { color: #000; }
.stat-divider { color: #ccc; }
.stat-failed { color: #cc6600; }

/* ── Filter tabs ───────────────────────────────────────────────────────── */
.filter-tabs {
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.filter-tab {
  padding: 6px 14px;
  border: 1px solid #ddd;
  background: #fff;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  cursor: pointer;
  color: #666;
  border-radius: 2px;
  transition: all 0.15s;
}

.filter-tab:hover { border-color: #999; color: #000; }
.filter-tab.active { background: #000; color: #fff; border-color: #000; }

/* ── Result cards ──────────────────────────────────────────────────────── */
.result-list {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.result-card {
  border-bottom: 1px solid #eee;
  padding: 20px 0;
}

.result-card:last-child { border-bottom: none; }

.result-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  flex-wrap: wrap;
}

.engine-badge {
  font-family: var(--font-mono);
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 2px 7px;
  border-radius: 2px;
  text-transform: uppercase;
}

.badge-duckduckgo { background: #de5833; color: #fff; }
.badge-reddit     { background: #ff4500; color: #fff; }
.badge-arxiv      { background: #2980b9; color: #fff; }
.badge-archive_org { background: #27ae60; color: #fff; }
.badge-ahmia      { background: #8e44ad; color: #fff; }
.badge-github     { background: #1a1a1a; color: #fff; }
.badge-brave      { background: #fb542b; color: #fff; }
.badge-searxng    { background: #3498db; color: #fff; }

.result-date, .result-extra {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #aaa;
}

.result-title {
  display: block;
  font-size: 1.15rem;
  font-weight: 600;
  color: #1a0dab;
  text-decoration: none;
  line-height: 1.3;
  margin-bottom: 4px;
}

.result-title:hover { text-decoration: underline; color: #0000cc; }

.result-url {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  color: #3c8f3c;
  margin-bottom: 6px;
  word-break: break-all;
}

.result-snippet {
  font-size: 0.9rem;
  color: #444;
  line-height: 1.6;
  margin: 0 0 10px;
}

.result-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.action-link {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #666;
  text-decoration: none;
  cursor: pointer;
  background: none;
  border: none;
  padding: 0;
  transition: color 0.15s;
}

.action-link:hover { color: #000; }
.archive-link:hover { color: #27ae60; }
.fetch-link:hover { color: #8e44ad; }
.fetch-link:disabled { color: #bbb; cursor: default; }

/* ── Expanded article text ─────────────────────────────────────────────── */
.article-body {
  margin-top: 14px;
  border: 1px solid #eee;
  background: #fafafa;
}

.article-body-header {
  font-family: var(--font-mono);
  font-size: 0.7rem;
  color: #888;
  padding: 8px 14px;
  border-bottom: 1px solid #eee;
  background: #f0f0f0;
}

.article-text {
  padding: 14px;
  font-family: var(--font-mono);
  font-size: 0.8rem;
  line-height: 1.7;
  color: #222;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.no-results {
  padding: 40px 0;
  color: #aaa;
  font-family: var(--font-mono);
  font-size: 0.85rem;
}

/* ── Engines info panel ────────────────────────────────────────────────── */
.engines-panel {
  max-width: 860px;
  margin: 0 auto;
  padding: 0 24px 80px;
}

.engines-header {
  font-family: var(--font-mono);
  font-size: 0.78rem;
  color: #999;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 20px;
  border-top: 1px solid #eee;
  padding-top: 40px;
  letter-spacing: 1px;
}

.diamond { font-size: 1.2rem; }

.engines-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 1px;
  background: #eee;
  border: 1px solid #eee;
}

.engine-card {
  background: #fff;
  padding: 18px;
  border: none;
}

.engine-name {
  font-weight: 700;
  font-size: 0.95rem;
  margin-bottom: 3px;
}

.engine-cat {
  font-family: var(--font-mono);
  font-size: 0.65rem;
  color: #aaa;
  letter-spacing: 1px;
  text-transform: uppercase;
  margin-bottom: 8px;
}

.engine-desc {
  font-size: 0.82rem;
  color: #666;
  line-height: 1.5;
}

.cat-bg-deep .engine-cat    { color: #8e44ad; }
.cat-bg-social .engine-cat  { color: #e67e22; }
.cat-bg-academic .engine-cat { color: #2980b9; }
.cat-bg-technical .engine-cat { color: #27ae60; }

/* ── Responsive ────────────────────────────────────────────────────────── */
@media (max-width: 640px) {
  .hero-title { font-size: 2.6rem; }
  .navbar { padding: 0 20px; }
  .search-hero { padding: 40px 16px 24px; }
  .results-area, .engines-panel { padding-left: 16px; padding-right: 16px; }
}
</style>
