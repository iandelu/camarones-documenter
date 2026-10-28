// Markdown → page: heading anchors, highlighted code, callouts, Mermaid (clickable, with zoom), embedded LikeC4 views,
// `:::` directives, live tables, the business/technical switch and the page outline. Moved from legacy/doc.js; the
// vendor libraries (marked, DOMPurify, highlight.js, Mermaid) are the page's own scripts (index.html).
import { docsGet } from '../docsApi.js'
import * as directives from './directives.js'
import * as generated from './generated.js'
import * as tables from './tables.js'
import { core } from '../core.js'

const $ = (s, el = document) => el.querySelector(s)
const $$ = (s, el = document) => [...el.querySelectorAll(s)]
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]))
const t = (k, vars) => core.t(k, vars)
const index = () => core.tree()

// The same rule as lib/docs.py slugify: lower case, letters/digits/space/_/- kept, spaces → -.
export const slugify = (s) => String(s).toLowerCase().trim().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s+/g, '-')
const CALLOUTS = ['note', 'tip', 'important', 'warning', 'caution']

// docs/flows/<slug>.md ↔ LikeC4 `dynamic view flow_<slug>` (CONVENTIONS: one dynamic view per business flow)
export const flowViewId = (path) => {
  const m = path.match(/^flows\/(.+)\.md$/)
  return m && m[1] !== 'index' ? 'flow_' + m[1].replace(/\W/g, '_') : null
}

export const isDark = () => (document.documentElement.dataset.theme
  || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark'

export function render(md, docPath, blocks = []) {
  const body = md.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '').replace(/^\s*#\s+.+\n/, '')   // the page header shows the title
  const el = document.createElement('div')
  el.className = 'doc'
  const toHtml = (s) => window.marked.parse(s, { gfm: true })
  el.innerHTML = window.DOMPurify.sanitize(directives.render(generated.mark(body, blocks, t), toHtml), { ADD_ATTR: ['hidden', 'role'] })
  const hrefFor = core.hrefFor
  const base = docPath.split('/').slice(0, -1)
  const resolve = (href) => {
    const parts = [...base]
    for (const p of href.split('/')) { if (p === '..') parts.pop(); else if (p && p !== '.') parts.push(p) }
    return parts.join('/')
  }

  const seen = {}
  $$('h1, h2, h3, h4', el).forEach((h) => {
    let s = slugify(h.textContent) || 'section'
    if (s in seen) s += '-' + (++seen[s]); else seen[s] = 0
    h.id = 'h-' + s                        // prefixed: a heading called "main" must not clash with the app's ids
    h.dataset.title = h.textContent
    h.insertAdjacentHTML('beforeend', `<a class="anchor" href="${esc(hrefFor(docPath, s))}" aria-hidden="true" tabindex="-1">#</a>`)
  })

  $$('a[href]', el).forEach((a) => {
    if (a.classList.contains('anchor')) return
    const href = a.getAttribute('href')
    if (/^#\//.test(href) || href.startsWith('/')) return
    if (href.startsWith('#')) { a.setAttribute('href', hrefFor(docPath, slugify(decodeURIComponent(href.slice(1))))); return }
    if (/^[a-z][\w+.-]*:/i.test(href)) { a.target = '_blank'; a.rel = 'noopener'; return }
    const [file, anchor] = href.split('#')
    if (file.endsWith('.md')) a.setAttribute('href', hrefFor(resolve(file), anchor ? slugify(anchor) : ''))
  })
  $$('img[src]', el).forEach((img) => {
    const src = img.getAttribute('src')
    if (!/^[a-z]+:|^\//i.test(src)) img.src = 'raw/' + resolve(src)
  })

  $$('pre code.language-mermaid', el).forEach((c) => {
    c.parentElement.replaceWith(figure(`<div class="mermaid">${esc(c.textContent)}</div>`, 'diagram'))
  })
  $$('pre code.language-likec4-view', el).forEach((c) => { c.parentElement.replaceWith(c4Box(c.textContent.trim())) })
  const flow = flowViewId(docPath)
  if (flow && (index().views || []).some((v) => v.id === flow) && !$(`.c4embed[data-view="${flow}"]`, el)) {
    const first = el.firstElementChild
    if (first?.tagName === 'P') first.after(c4Box(flow)); else el.prepend(c4Box(flow))
  }

  $$('pre > code', el).forEach((c) => {
    const langClass = [...c.classList].find((k) => k.startsWith('language-'))
    if (langClass && window.hljs?.getLanguage(langClass.slice(9))) {
      try { window.hljs.highlightElement(c) } catch { /* plain code is fine */ }
    }
    const pre = c.parentElement
    pre.classList.add('code')
    pre.insertAdjacentHTML('beforeend', `<button class="copy ghost small" type="button">${esc(t('copy'))}</button>`)
  })

  $$('blockquote', el).forEach((q) => {
    const p = q.firstElementChild
    const m = p?.tagName === 'P' && p.innerHTML.match(/^\s*\[!(\w+)\]\s*(<br>)?\s*/)
    const kind = m && m[1].toLowerCase()
    if (!CALLOUTS.includes(kind)) return
    p.innerHTML = p.innerHTML.slice(m[0].length)
    if (!p.textContent.trim()) p.remove()
    q.className = `callout ${kind}`
    q.insertAdjacentHTML('afterbegin', `<div class="callout-title">${esc(t('callout.' + kind))}</div>`)
  })

  $$('table', el).forEach((tb) => {
    const wrap = document.createElement('div')
    wrap.className = 'tablewrap'
    tb.replaceWith(wrap)
    wrap.append(tb)
    tables.enhance(tb, { filter: t('filter'), sort: t('sortBy') })
  })
  return el
}

function figure(inner, cls) {
  const f = document.createElement('figure')
  f.className = cls
  f.innerHTML = `${inner}<button class="zoom ghost small" type="button" title="${esc(t('zoom'))}" aria-label="${esc(t('zoom'))}">⤢</button>`
  return f
}

export function c4Box(id) {
  const d = document.createElement('div')
  d.className = 'c4embed'
  d.dataset.view = id
  return d
}

// Mermaid draws at 100% of the column, so a wide sequence shrinks to unreadable. Shrink at most to MIN_SCALE of
// its natural size (text stays legible), scroll beyond that, and let a click open it full screen with zoom and pan.
const MIN_SCALE = 0.65
export async function drawMermaid(root) {
  const nodes = $$('.mermaid', root)
  if (!nodes.length || !window.mermaid) return
  try { await window.mermaid.run({ nodes }) } catch (e) { console.warn(e) }
  nodes.forEach((n) => {
    const svg = $('svg', n)
    const natural = svg && parseFloat(svg.style.maxWidth)
    if (!natural) return
    const room = n.parentElement.clientWidth - 32
    svg.style.width = `${Math.round(natural <= room ? natural : Math.max(room, natural * MIN_SCALE))}px`
    svg.style.maxWidth = 'none'
    svg.removeAttribute('width')
  })
}

// ---------- the zoom dialog (#zoomer, in index.html): pan with the pointer, zoom with the wheel or its buttons ----------
const ZOOM = { k: 1, x: 0, y: 0, drag: null }
const zoomApply = () => { $('#zoomer-stage').style.transform = `translate(${ZOOM.x}px, ${ZOOM.y}px) scale(${ZOOM.k})` }
function zoomFit() {
  const body = $('#zoomer-body').getBoundingClientRect()
  const stage = $('#zoomer-stage')
  stage.style.transform = 'none'
  const r = stage.getBoundingClientRect()
  ZOOM.k = Math.min(body.width / r.width, body.height / r.height, 4) * 0.95
  ZOOM.x = (body.width - r.width * ZOOM.k) / 2
  ZOOM.y = (body.height - r.height * ZOOM.k) / 2
  zoomApply()
}
function zoomBy(f, cx, cy) {
  const body = $('#zoomer-body').getBoundingClientRect()
  const x = (cx ?? body.width / 2), y = (cy ?? body.height / 2)
  const k = Math.min(Math.max(ZOOM.k * f, 0.1), 12)
  ZOOM.x = x - (x - ZOOM.x) * (k / ZOOM.k)
  ZOOM.y = y - (y - ZOOM.y) * (k / ZOOM.k)
  ZOOM.k = k
  zoomApply()
}
function openZoom(fig) {
  const svg = $('.mermaid svg', fig)
  if (!svg) return
  const copy = svg.cloneNode(true)                 // keeps its id: Mermaid scopes the diagram's CSS to it
  $('#zoomer-body').innerHTML = '<div id="zoomer-stage"></div>'
  $('#zoomer-stage').append(copy)
  $('#zoomer').showModal()
  requestAnimationFrame(zoomFit)
}

// ---------- LikeC4: `likec4 build` also emits likec4-views.js, a web component (<likec4-view view-id>) ----------
let likec4Ready = null
function loadLikeC4() {
  likec4Ready ||= new Promise((ok) => {
    if (customElements.get('likec4-view')) return ok(true)
    const s = document.createElement('script')
    s.src = 'architecture/likec4-views.js'
    s.onload = () => ok(!!customElements.get('likec4-view'))
    s.onerror = () => ok(false)
    document.head.append(s)
  })
  return likec4Ready
}

let viewersAnswer = null
export const loadViewers = (fresh = false) => (fresh || !viewersAnswer ? (viewersAnswer = docsGet('viewers')) : viewersAnswer)

function c4View(id) {
  const v = document.createElement('likec4-view')
  v.setAttribute('view-id', id)
  v.setAttribute('browser', 'true')
  v.setAttribute('color-scheme', isDark() ? 'dark' : 'light')
  return v
}

// The component keeps the diagram's aspect ratio at full width, so a tall view would fill several screens. It does not
// re-fit when narrowed afterwards: measure the ratio on a hidden copy, then mount the real one at the width that fits.
function placeC4(box, id, maxH) {
  let ratio = 0, width = 0, tries = 0
  const make = (w, probe = false) => {
    const el = c4View(id)
    el.style.width = `${w}px`
    if (probe) el.classList.add('probe')
    else $$('likec4-view', box).forEach((x) => x.remove())
    box.append(el)
    return el
  }
  const target = () => Math.round(Math.min(box.clientWidth, maxH() * ratio))
  const probe = make(box.clientWidth, true)
  const measure = () => {
    const inner = probe.shadowRoot?.querySelector('.likec4-view')
    const m = inner && getComputedStyle(inner).aspectRatio.match(/([\d.]+)\s*\/\s*([\d.]+)/)
    if (!m) { if (tries++ < 100) setTimeout(measure, 50); return }
    ratio = m[1] / m[2]
    width = target()
    make(width)
    let h
    new ResizeObserver(() => {
      clearTimeout(h)
      h = setTimeout(() => { const w = target(); if (Math.abs(w - width) > 40) { width = w; make(w) } }, 200)
    }).observe(box)
  }
  measure()
}

export async function c4Available() {
  const v = (await loadViewers()).c4
  return { v, ok: v.exists && await loadLikeC4() }
}

function c4Missing(box, v) {
  if (core.mode() === 'static') { box.remove(); return }
  box.innerHTML = `<div class="c4missing"><span class="muted">${esc(v.exists ? t('c4Unavailable') : t('c4Missing'))}</span></div>`
}

const EMBED_MAX_H = () => Math.min(innerHeight * 0.75, 760)

export async function drawC4(root, { caption = true, maxH = EMBED_MAX_H } = {}) {
  const boxes = $$('.c4embed', root)
  if (!boxes.length) return
  const { v, ok } = await c4Available()
  for (const box of boxes) {
    const id = box.dataset.view
    const view = (index().views || []).find((x) => x.id === id)
    if (!view) { box.innerHTML = `<div class="c4missing muted">C4 · <code>${esc(id)}</code> ?</div>`; continue }
    if (!ok) { c4Missing(box, v); continue }
    box.innerHTML = caption ? `<div class="c4cap"><b>${esc(view.title)}</b><span class="muted small">${esc(t('diagram'))}</span>
      <a href="#/c4/${esc(id)}">${esc(t('viewIn'))} <span aria-hidden="true">→</span></a></div>` : ''
    placeC4(box, id, maxH)
  }
}

// ---------- outline: the page's h2/h3 in #toc, the one in view marked as you scroll ----------
let tocObserver = null
export function drawToc(root) {
  tocObserver?.disconnect()
  const toc = $('#toc')
  if (!toc) return                        // a view without an outline slot
  const hs = root ? $$('h2, h3', root) : []
  toc.classList.toggle('empty', hs.length < 2)
  if (hs.length < 2) { toc.innerHTML = ''; return }
  toc.innerHTML = `<div class="toc-title">${esc(t('onThisPage'))}</div>` + hs.map((h) =>
    `<a href="${esc($('.anchor', h).getAttribute('href'))}" data-id="${esc(h.id)}" class="l${h.tagName[1]}">${esc(h.dataset.title)}</a>`).join('')
  tocObserver = new IntersectionObserver((entries) => {
    const hit = entries.find((e) => e.isIntersecting)
    if (hit) $$('#toc a').forEach((a) => a.classList.toggle('on', a.dataset.id === hit.target.id))
  }, { rootMargin: '-72px 0px -70% 0px' })
  hs.forEach((h) => tocObserver.observe(h))
}

export function scrollToAnchor(anchor) {
  const h = anchor && document.getElementById('h-' + anchor)
  if (h) h.scrollIntoView({ block: 'start' }); else window.scrollTo(0, 0)
}

// ---------- business / technical: `:::tech` and `:::business` blocks follow the reader's choice ----------
const audience = () => { try { return localStorage.getItem('cam-audience') || 'all' } catch { return 'all' } }
function applyAudience() {
  document.body.dataset.audience = audience()
  $$('.audience button').forEach((b) => b.classList.toggle('on', b.dataset.audience === document.body.dataset.audience))
}
function audienceSwitch(el) {
  if (!$('[data-audience]', el)) return
  el.insertAdjacentHTML('afterbegin', `<div class="audience seg" role="group" title="${esc(t('audienceHint'))}">
    <button type="button" data-audience="all">${esc(t('audienceAll'))}</button>
    <button type="button" data-audience="business">${esc(t('audienceBusiness'))}</button></div>`)
  applyAudience()
}

// ---------- clickable diagrams: a node or participant named like a page (or a repo) opens it ----------
function diagramTargets() {
  const map = {}
  const byPath = (p) => core.byPath(p)
  for (const d of index().docs || []) if ((d.space || 'docs') === 'docs') map[d.title.toLowerCase()] ||= d.path
  for (const r of index().repos || []) {
    const page = `repos/${r}/index.md`, brief = `repos/${r}/brief.md`, ref = `repos/${r}/reference.md`   // the repo page first
    map[r.toLowerCase()] ||= byPath(page) ? page : byPath(brief) ? brief : byPath(ref) ? ref : undefined
  }
  return map
}
function linkDiagrams(root) {
  const targets = diagramTargets()
  $$('.mermaid svg', root).forEach((svg) => {
    $$('g.node, g.actor, text.actor, g[class*="actor"]', svg).forEach((n) => {
      const path = targets[n.textContent.trim().toLowerCase()]
      if (!path) return
      n.classList.add('mm-link')
      n.dataset.href = core.hrefFor(path)
      n.setAttribute('role', 'link')
    })
  })
}

// Render, then everything that needs the element in the DOM.
export async function mountDoc(container, raw, path, anchor, blocks = []) {
  const el = render(raw, path, blocks)
  container.append(el)
  audienceSwitch(el)
  drawToc(el)
  scrollToAnchor(anchor)
  await drawMermaid(el)
  linkDiagrams(el)
  await drawC4(el)
  if (anchor) scrollToAnchor(anchor)
  return el
}

// Copy buttons, clickable diagrams, `:::tabs`, the in-page audience switch and diagram zoom, for every page (event
// delegation), and the zoom dialog's controls. Once, when the portal starts.
let wired = false
export function wireDocs() {
  if (wired) return
  wired = true
  document.addEventListener('click', async (e) => {
    const copy = e.target.closest('pre.code .copy')
    if (copy) {
      try { await navigator.clipboard.writeText(copy.parentElement.querySelector('code').textContent); copy.textContent = t('copied') }
      catch { /* clipboard blocked: nothing to do */ }
      setTimeout(() => { copy.textContent = t('copy') }, 1500)
      return
    }
    const link = e.target.closest('.mm-link')
    if (link) { location.hash = link.dataset.href; return }
    const tab = e.target.closest('.dv-tablist button')
    if (tab) {
      const box = tab.closest('.dv-tabs')
      $$('.dv-tablist button', box).forEach((b) => b.classList.toggle('on', b === tab))
      $$('.dv-tab', box).forEach((p) => { p.hidden = p.dataset.tab !== tab.dataset.tab })
      return
    }
    const aud = e.target.closest('.doc .audience button')
    if (aud) {
      try { localStorage.setItem('cam-audience', aud.dataset.audience) } catch { /* private mode */ }
      applyAudience()
      return
    }
    const fig = e.target.closest('figure.diagram')
    if (fig && !e.target.closest('a')) openZoom(fig)
  })
  const zoomer = $('#zoomer')
  const zbody = $('#zoomer-body')
  if (!zoomer || !zbody) return
  zbody.addEventListener('wheel', (e) => {
    e.preventDefault()
    const r = zbody.getBoundingClientRect()
    zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top)
  }, { passive: false })
  zbody.addEventListener('pointerdown', (e) => { ZOOM.drag = { x: e.clientX - ZOOM.x, y: e.clientY - ZOOM.y }; zbody.setPointerCapture(e.pointerId) })
  zbody.addEventListener('pointermove', (e) => { if (ZOOM.drag) { ZOOM.x = e.clientX - ZOOM.drag.x; ZOOM.y = e.clientY - ZOOM.drag.y; zoomApply() } })
  zbody.addEventListener('pointerup', () => { ZOOM.drag = null })
  $('#zoom-in').onclick = () => zoomBy(1.25)
  $('#zoom-out').onclick = () => zoomBy(0.8)
  $('#zoom-fit').onclick = zoomFit
  zoomer.addEventListener('click', (e) => { if (e.target === zoomer || e.target.closest('#zoomer-close')) zoomer.close() })
}
