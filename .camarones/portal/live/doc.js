'use strict';
// Markdown → page: heading anchors, highlighted code, callouts, Mermaid, embedded LikeC4 views and the page outline.

const slugify = (s) => String(s).toLowerCase().trim().replace(/[^\p{L}\p{N}\s_-]/gu, '').replace(/\s+/g, '-');
const CALLOUTS = ['note', 'tip', 'important', 'warning', 'caution'];

// docs/flows/<slug>.md ↔ LikeC4 `dynamic view flow_<slug>` (CONVENTIONS: one dynamic view per business flow)
const flowViewId = (path) => {
  const m = path.match(/^flows\/(.+)\.md$/);
  return m && m[1] !== 'index' ? 'flow_' + m[1].replace(/\W/g, '_') : null;
};

function render(md, docPath) {
  const body = md.replace(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/, '').replace(/^\s*#\s+.+\n/, '');   // the page header shows the title
  const el = document.createElement('div');
  el.className = 'doc';
  el.innerHTML = DOMPurify.sanitize(marked.parse(body, { gfm: true }));
  const base = docPath.split('/').slice(0, -1);
  const resolve = (href) => {
    const parts = [...base];
    for (const p of href.split('/')) { if (p === '..') parts.pop(); else if (p && p !== '.') parts.push(p); }
    return parts.join('/');
  };

  const seen = {};
  $$('h1, h2, h3, h4', el).forEach((h) => {
    let s = slugify(h.textContent) || 'section';
    if (s in seen) s += '-' + (++seen[s]); else seen[s] = 0;
    h.id = 'h-' + s;                       // prefixed: a heading called "main" must not clash with the app's ids
    h.dataset.title = h.textContent;
    h.insertAdjacentHTML('beforeend', `<a class="anchor" href="${esc(hrefFor(docPath, s))}" aria-hidden="true">#</a>`);
  });

  $$('a[href]', el).forEach((a) => {
    if (a.classList.contains('anchor')) return;
    const href = a.getAttribute('href');
    if (/^#\//.test(href) || href.startsWith('/')) return;
    if (href.startsWith('#')) { a.setAttribute('href', hrefFor(docPath, slugify(decodeURIComponent(href.slice(1))))); return; }
    if (/^[a-z][\w+.-]*:/i.test(href)) { a.target = '_blank'; a.rel = 'noopener'; return; }
    const [file, anchor] = href.split('#');
    if (file.endsWith('.md')) a.setAttribute('href', hrefFor(resolve(file), anchor ? slugify(anchor) : ''));
  });
  $$('img[src]', el).forEach((img) => {
    const src = img.getAttribute('src');
    if (!/^[a-z]+:|^\//i.test(src)) img.src = 'raw/' + resolve(src);
  });

  $$('pre code.language-mermaid', el).forEach((c) => {
    c.parentElement.replaceWith(figure(`<div class="mermaid">${esc(c.textContent)}</div>`, 'diagram'));
  });
  $$('pre code.language-likec4-view', el).forEach((c) => {
    c.parentElement.replaceWith(c4Box(c.textContent.trim()));
  });
  const flow = flowViewId(docPath);
  if (flow && T.views.some((v) => v.id === flow) && !$(`.c4embed[data-view="${flow}"]`, el)) {
    const first = el.firstElementChild;
    if (first?.tagName === 'P') first.after(c4Box(flow)); else el.prepend(c4Box(flow));
  }

  $$('pre > code', el).forEach((c) => {
    const langClass = [...c.classList].find((k) => k.startsWith('language-'));
    if (langClass && window.hljs?.getLanguage(langClass.slice(9))) {
      try { hljs.highlightElement(c); } catch { /* plain code is fine */ }
    }
    const pre = c.parentElement;
    pre.classList.add('code');
    pre.insertAdjacentHTML('beforeend', `<button class="copy ghost small" type="button">${esc(t('copy'))}</button>`);
  });

  $$('blockquote', el).forEach((q) => {
    const p = q.firstElementChild;
    const m = p?.tagName === 'P' && p.innerHTML.match(/^\s*\[!(\w+)\]\s*(<br>)?\s*/);
    const kind = m && m[1].toLowerCase();
    if (!CALLOUTS.includes(kind)) return;
    p.innerHTML = p.innerHTML.slice(m[0].length);
    if (!p.textContent.trim()) p.remove();
    q.className = `callout ${kind}`;
    q.insertAdjacentHTML('afterbegin', `<div class="callout-title">${esc(t('callout.' + kind))}</div>`);
  });

  $$('table', el).forEach((tb) => {
    const wrap = document.createElement('div');
    wrap.className = 'tablewrap';
    tb.replaceWith(wrap);
    wrap.append(tb);
  });
  return el;
}

function figure(inner, cls) {
  const f = document.createElement('figure');
  f.className = cls;
  f.innerHTML = `${inner}<button class="zoom ghost small" type="button" title="${esc(t('zoom'))}">⤢</button>`;
  return f;
}

function c4Box(id) {
  const d = document.createElement('div');
  d.className = 'c4embed';
  d.dataset.view = id;
  return d;
}

// Mermaid draws at 100% of the column, so a wide sequence shrinks to unreadable: keep its natural size (the figure
// scrolls) and let a click open it full screen with zoom and pan.
async function drawMermaid(root) {
  const nodes = $$('.mermaid', root);
  if (!nodes.length || !window.mermaid) return;
  try { await mermaid.run({ nodes }); } catch (e) { console.warn(e); }
  nodes.forEach((n) => {
    const svg = $('svg', n);
    const natural = svg && parseFloat(svg.style.maxWidth);
    if (natural) { svg.style.width = `${natural}px`; svg.style.maxWidth = 'none'; svg.removeAttribute('width'); }
  });
}

const ZOOM = { k: 1, x: 0, y: 0, drag: null };
function zoomApply() { $('#zoomer-stage').style.transform = `translate(${ZOOM.x}px, ${ZOOM.y}px) scale(${ZOOM.k})`; }
function zoomFit() {
  const body = $('#zoomer-body').getBoundingClientRect();
  const stage = $('#zoomer-stage');
  stage.style.transform = 'none';
  const r = stage.getBoundingClientRect();
  ZOOM.k = Math.min(body.width / r.width, body.height / r.height, 4) * 0.95;
  ZOOM.x = (body.width - r.width * ZOOM.k) / 2;
  ZOOM.y = (body.height - r.height * ZOOM.k) / 2;
  zoomApply();
}
function zoomBy(f, cx, cy) {
  const body = $('#zoomer-body').getBoundingClientRect();
  const x = (cx ?? body.width / 2), y = (cy ?? body.height / 2);
  const k = Math.min(Math.max(ZOOM.k * f, 0.1), 12);
  ZOOM.x = x - (x - ZOOM.x) * (k / ZOOM.k);
  ZOOM.y = y - (y - ZOOM.y) * (k / ZOOM.k);
  ZOOM.k = k;
  zoomApply();
}
function openZoom(fig) {
  const svg = $('.mermaid svg', fig);
  if (!svg) return;
  const copy = svg.cloneNode(true);                 // keeps its id: Mermaid scopes the diagram's CSS to it
  $('#zoomer-body').innerHTML = '<div id="zoomer-stage"></div>';
  $('#zoomer-stage').append(copy);
  $('#zoomer').showModal();
  requestAnimationFrame(zoomFit);
}
const zbody = $('#zoomer-body');
zbody.addEventListener('wheel', (e) => {
  e.preventDefault();
  const r = zbody.getBoundingClientRect();
  zoomBy(Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top);
}, { passive: false });
zbody.addEventListener('pointerdown', (e) => { ZOOM.drag = { x: e.clientX - ZOOM.x, y: e.clientY - ZOOM.y }; zbody.setPointerCapture(e.pointerId); });
zbody.addEventListener('pointermove', (e) => { if (ZOOM.drag) { ZOOM.x = e.clientX - ZOOM.drag.x; ZOOM.y = e.clientY - ZOOM.drag.y; zoomApply(); } });
zbody.addEventListener('pointerup', () => { ZOOM.drag = null; });
$('#zoom-in').onclick = () => zoomBy(1.25);
$('#zoom-out').onclick = () => zoomBy(0.8);
$('#zoom-fit').onclick = zoomFit;

// ---------- LikeC4: `likec4 build` also emits likec4-views.js, a web component (<likec4-view view-id>) ----------
let likec4Ready = null;
function loadLikeC4() {
  likec4Ready ||= new Promise((resolve) => {
    if (customElements.get('likec4-view')) return resolve(true);
    const s = document.createElement('script');
    s.src = 'architecture/likec4-views.js';
    s.onload = () => resolve(!!customElements.get('likec4-view'));
    s.onerror = () => resolve(false);
    document.head.append(s);
  });
  return likec4Ready;
}

function c4View(id) {
  const v = document.createElement('likec4-view');
  v.setAttribute('view-id', id);
  v.setAttribute('browser', 'true');
  v.setAttribute('color-scheme', isDark() ? 'dark' : 'light');
  return v;
}

// The component keeps the diagram's aspect ratio at full width, so a tall view would fill several screens. It does not
// re-fit when narrowed afterwards: measure the ratio on a hidden copy, then mount the real one at the width that fits.
function placeC4(box, id, maxH) {
  let ratio = 0, width = 0, tries = 0;
  const make = (w, probe = false) => {
    const el = c4View(id);
    el.style.width = `${w}px`;
    if (probe) el.classList.add('probe');
    else $$('likec4-view', box).forEach((x) => x.remove());
    box.append(el);
    return el;
  };
  const target = () => Math.round(Math.min(box.clientWidth, maxH() * ratio));
  const probe = make(box.clientWidth, true);
  const measure = () => {
    const inner = probe.shadowRoot?.querySelector('.likec4-view');
    const m = inner && getComputedStyle(inner).aspectRatio.match(/([\d.]+)\s*\/\s*([\d.]+)/);
    if (!m) { if (tries++ < 100) setTimeout(measure, 50); return; }
    ratio = m[1] / m[2];
    width = target();
    make(width);
    let h;
    new ResizeObserver(() => {
      clearTimeout(h);
      h = setTimeout(() => { const w = target(); if (Math.abs(w - width) > 40) { width = w; make(w); } }, 200);
    }).observe(box);
  };
  measure();
}

async function c4Available() {
  const v = (await loadViewers()).c4;
  return { v, ok: v.exists && await loadLikeC4() };
}

function c4Missing(box, v) {
  if (STATIC) { box.remove(); return; }
  box.innerHTML = `<div class="c4missing"><span class="muted">${esc(v.exists ? t('c4Unavailable') : t('c4Missing'))}</span>
    ${v.model ? `<button class="small" type="button">${esc(v.exists ? t('rebuild') : t('build'))}</button>` : ''}
    <pre class="joblog" hidden></pre></div>`;
  box.querySelector('button')?.addEventListener('click', (e) =>
    startBuild('c4', '', e.target, box.querySelector('pre'), () => location.reload()));
}

const EMBED_MAX_H = () => Math.min(innerHeight * 0.75, 760);

async function drawC4(root, { caption = true, maxH = EMBED_MAX_H } = {}) {
  const boxes = $$('.c4embed', root);
  if (!boxes.length) return;
  const { v, ok } = await c4Available();
  for (const box of boxes) {
    const id = box.dataset.view;
    const view = T.views.find((x) => x.id === id);
    if (!view) { box.innerHTML = `<div class="c4missing muted">C4 · <code>${esc(id)}</code> ?</div>`; continue; }
    if (!ok) { c4Missing(box, v); continue; }
    box.innerHTML = caption ? `<div class="c4cap"><b>${esc(view.title)}</b><span class="muted small">${esc(t('diagram'))}</span>
      <a href="#/c4/${esc(id)}">${esc(t('viewIn'))} →</a></div>` : '';
    placeC4(box, id, maxH);
  }
}

// ---------- outline ----------
let tocObserver = null;
function drawToc(root) {
  tocObserver?.disconnect();
  const toc = $('#toc');
  const hs = root ? $$('h2, h3', root) : [];
  toc.classList.toggle('empty', hs.length < 2);
  if (hs.length < 2) { toc.innerHTML = ''; return; }
  toc.innerHTML = `<div class="toc-title">${esc(t('onThisPage'))}</div>` + hs.map((h) =>
    `<a href="${esc($('.anchor', h).getAttribute('href'))}" data-id="${esc(h.id)}" class="l${h.tagName[1]}">${esc(h.dataset.title)}</a>`).join('');
  tocObserver = new IntersectionObserver((entries) => {
    const hit = entries.find((e) => e.isIntersecting);
    if (hit) $$('#toc a').forEach((a) => a.classList.toggle('on', a.dataset.id === hit.target.id));
  }, { rootMargin: '-72px 0px -70% 0px' });
  hs.forEach((h) => tocObserver.observe(h));
}

function scrollToAnchor(anchor) {
  const h = anchor && document.getElementById('h-' + anchor);
  if (h) h.scrollIntoView({ block: 'start' }); else window.scrollTo(0, 0);
}

// Render, then everything that needs the element in the DOM.
async function mountDoc(container, raw, path, anchor) {
  const el = render(raw, path);
  container.append(el);
  drawToc(el);
  scrollToAnchor(anchor);
  await drawMermaid(el);
  await drawC4(el);
  if (anchor) scrollToAnchor(anchor);
  return el;
}

// Copy buttons and diagram zoom, for every page (event delegation).
document.addEventListener('click', async (e) => {
  const copy = e.target.closest('pre.code .copy');
  if (copy) {
    try { await navigator.clipboard.writeText(copy.parentElement.querySelector('code').textContent); copy.textContent = t('copied'); }
    catch { /* clipboard blocked: nothing to do */ }
    setTimeout(() => { copy.textContent = t('copy'); }, 1500);
    return;
  }
  const fig = e.target.closest('figure.diagram');
  if (fig && !e.target.closest('a')) openZoom(fig);
});
