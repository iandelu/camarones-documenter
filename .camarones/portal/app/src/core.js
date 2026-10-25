// The portal's state and the helpers every view uses: the docs index, the reader's language and theme, the strings
// (i18n/portal.js), a page's address, toasts. Moved from the plain scripts (legacy/core.js, legacy/app.js) in 4.52.
import { RUNS, STATIC } from './api.js'
import { docsGet } from './docsApi.js'
import { I18N } from './i18n/portal.js'

const store = {
  get: (k) => { try { return localStorage.getItem(k) || '' } catch { return '' } },
  set: (k, v) => { try { localStorage.setItem(k, v) } catch { /* private mode */ } },
}
const LANG_NAMES = { en: 'English', es: 'Español', fr: 'Français', de: 'Deutsch', pt: 'Português', it: 'Italiano' }

let T = { docs: [], langs: [], codeGraphs: [], engines: [], repos: [], sections: [], views: [], summary: {} }
let BY_PATH = {}
let lang = store.get('cam-lang')             // '' = English (canonical docs); otherwise a translation code
let CURRENT = ''                             // page on screen: a hash change that only moves the anchor just scrolls

const ui = () => I18N[lang] || I18N.en
const t = (k, vars = {}) => (ui()[k] ?? I18N.en[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '')
const has = (k) => (ui()[k] ?? I18N.en[k]) !== undefined
const ago = (sec) => {
  if (!sec) return ''
  const d = new Date(sec * 1000)
  return (Date.now() - d) < 60000 ? t('justNow') : d.toLocaleString(lang || 'en', { dateStyle: 'medium', timeStyle: 'short' })
}
const sectionLabel = (name) => (has('sec.' + name) ? t('sec.' + name) : name.replace(/[-_]/g, ' ').replace(/^./, (c) => c.toUpperCase()))

// A page's address: wiki pages live in their own space, everything else under Docs.
function hrefFor(path, anchor) {
  const a = anchor ? '::' + anchor : ''
  if (BY_PATH[path]?.space === 'wiki') {
    const [, repo, ...rest] = path.split('/')
    return `#/wiki/${repo}/${rest.join('/')}${a}`
  }
  return `#/docs/${path}${a}`
}

function toast(msg) {
  const el = document.getElementById('toast')
  if (!el) return
  el.textContent = msg
  el.hidden = false
  clearTimeout(toast.h)
  toast.h = setTimeout(() => { el.hidden = true }, 3500)
}

// ---------- theme: follows the OS until the reader picks one ----------
const isDark = () => (document.documentElement.dataset.theme
  || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark'
function applyTheme() {
  const pick = store.get('cam-theme')
  if (pick) document.documentElement.dataset.theme = pick; else delete document.documentElement.dataset.theme
  window.mermaid?.initialize({ startOnLoad: false, theme: isDark() ? 'dark' : 'neutral', securityLevel: 'strict',
    fontFamily: 'Inter, ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif' })
  document.querySelectorAll('likec4-view').forEach((v) => v.setAttribute('color-scheme', isDark() ? 'dark' : 'light'))
}

async function loadTree() {
  T = await docsGet('tree')
  T.sections ||= []
  T.views ||= []
  BY_PATH = Object.fromEntries(T.docs.map((d) => [d.path, { ...d, space: d.space || 'docs' }]))
  T.docs = Object.values(BY_PATH)
  if (!T.langs.includes(lang)) lang = ''
  document.title = `${T.project} — Camarón`
}

export const core = {
  // the docs index, and in the app whether this kit is a checkout with its tests (the Taller's Kit dev view);
  // the reader's language: the browser's on a first visit, when the docs are translated to it
  async boot() {
    applyTheme()
    await loadTree()
    if (RUNS) await docsGet('app/info').then((i) => { T.kitdev = i.kitdev }, () => {})
    if (!store.get('cam-lang')) {
      const nav = (navigator.language || 'en').slice(0, 2)
      if (T.langs.includes(nav)) lang = nav
    }
    document.documentElement.lang = lang || 'en'
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
      if (!store.get('cam-theme')) { applyTheme(); window.CamaronShell?.go() }
    })
  },
  current: () => CURRENT,
  setCurrent: (p) => { CURRENT = p },
  toast,
  ago,
  reload: loadTree,
  mode: () => (STATIC ? 'static' : RUNS ? 'app' : 'live'),
  isStatic: () => STATIC,
  tree: () => T,
  byPath: (p) => BY_PATH[p],
  hrefFor,
  t,
  sectionLabel,
  lang: () => lang,
  langName: (l) => LANG_NAMES[l] || l,
  setLang(l) { lang = l; store.set('cam-lang', l); document.documentElement.lang = l || 'en'; CURRENT = '' },
  toggleTheme() { store.set('cam-theme', isDark() ? 'light' : 'dark'); applyTheme(); CURRENT = '' },
  isDark,
}
