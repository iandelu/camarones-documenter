import { STATIC } from './api.js'

// Reading the docs API the same way in both portals: the live server (lib/serve.py, GET api/<name>?<params>) and the
// static export, where each answer is a json file (api/<name>.json, api/doc/<lang|_>/<path>.json) and search runs
// here over api/search.json. Reads only; writes go through postJSON (api.js).
const where = () => ({ static: STATIC })

export async function docsGet(name, params = {}, mode = where()) {
  if (mode.static) return staticGet(name, params)
  const qs = new URLSearchParams(params).toString()
  const r = await fetch(`api/${name}${qs ? '?' + qs : ''}`)
  const data = await r.json()
  if (!r.ok) throw new Error(data.error || r.statusText)
  return data
}

async function json(url) {
  const r = await fetch(url)
  if (!r.ok) throw new Error(r.statusText)
  return r.json()
}

let searchIndex = null
async function staticGet(name, params) {
  if (name === 'doc') {
    const tryGet = async (l) => { const r = await fetch(`api/doc/${l || '_'}/${params.path}.json`); return r.ok ? r.json() : null }
    const d = params.lang && await tryGet(params.lang)
    if (d) return d
    const en = await tryGet('')
    if (!en) throw new Error(`unknown page ${params.path}`)
    return params.lang ? { ...en, lang: params.lang, exists: false, raw: '' } : en
  }
  if (name === 'search') {
    searchIndex ||= await json('api/search.json')
    return scoreSearch(searchIndex, params.q, params.lang || '')
  }
  if (name === 'codemap') return json(`api/codemap/${encodeURIComponent(params.repo)}.json`)
  return json(`api/${name}.json`)
}

// The export's search: each term (2+ letters) counts once per occurrence, a hit in the path weighs 5; up to three
// matching lines per page. The reader's language when the index has it, else English.
export function scoreSearch(index, q, lang) {
  const terms = ((q || '').toLowerCase().match(/\w+/g) || []).filter((w) => w.length > 1)
  if (!terms.length) return []
  const want = index.some((e) => e.lang === lang) ? lang : ''
  return index.filter((e) => e.lang === want).map((e) => {
    const low = e.text.toLowerCase()
    const score = terms.reduce((s, w) => s + low.split(w).length - 1 + (e.path.toLowerCase().includes(w) ? 5 : 0), 0)
    const lines = e.text.split('\n').filter((l) => terms.some((w) => l.toLowerCase().includes(w))).slice(0, 3).map((l) => l.trim().slice(0, 240))
    return { ...e, score, lines }
  }).filter((e) => e.score).sort((a, b) => b.score - a.score).slice(0, 20)
}
