import service from './index.js'

export async function listEngines() {
  const res = await service.get('/api/search/engines')
  return res
}

export async function searchQuery(query, engines = null, maxPerEngine = 8) {
  const body = { query, max_per_engine: maxPerEngine }
  if (engines && engines.length > 0) body.engines = engines
  const res = await service.post('/api/search/query', body)
  return res.data
}

export async function searchDeep(query, maxPerEngine = 10) {
  const res = await service.post('/api/search/deep', { query, max_per_engine: maxPerEngine })
  return res.data
}

export async function fetchArticleApi(url) {
  const res = await service.post('/api/search/fetch', { url })
  return res.data
}
