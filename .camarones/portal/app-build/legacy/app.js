'use strict';
// The views still painted by plain scripts into the shell's slots (#main, #toc, #tree): a page's chrome for the wikis (showPage).
// The shell (src/shell/Shell.jsx) owns the header, the sidebar's zones and the router; it calls these views through
// window.CamaronLegacy (bottom of this file) until each one moves to React.

let CURRENT = '';            // page on screen: a hash change that only moves the anchor just scrolls

// What the zones (src/zones.js) offer: the export, the live server, or the desktop app's window (which also has
// the Taller, where machine work runs).
const MODE = () => (STATIC ? 'static' : RUNS ? 'app' : 'live');

// The layout a view wants; the header and breadcrumbs are the shell's.
function drawChrome(active, { viewer = false, bare = false } = {}) {
  document.documentElement.lang = lang || 'en';
  document.body.classList.toggle('viewer-mode', viewer);
  document.body.classList.toggle('bare', bare);
  if (viewer) drawToc(null);
}

// ---------- a page with its chrome: React (src/views/Doc.jsx) for docs; this one stays for the wiki pages (wiki.js) ----------
async function showPage(path, anchor, ctx) {
  const d = await api('doc', { path, lang, track: 1 });
  const english = lang && !d.exists ? await api('doc', { path }) : null;
  const row = BY_PATH[path] || {};
  const i18n = lang ? (row.i18n || {})[lang] : '';
  const title = d.exists ? d.title : english?.title || row.title || d.title;
  const edit = STATIC
    ? (T.editBase ? `<a class="button ghost small" href="${esc(T.editBase + d.file)}" target="_blank" rel="noopener">✎ ${esc(t('editForge'))} ↗</a>` : '')
    : `<button id="a-edit" class="ghost small" type="button">✎ ${esc(t('edit'))}</button>
       ${d.trust !== 'confirmed' ? `<button id="a-confirm" class="ghost small" type="button">${esc(t('confirm'))}</button>` : ''}
       <button id="a-fb" class="ghost small" type="button">${esc(t('requestChange'))}</button>`;
  const i = ctx.order.indexOf(path);
  const pager = (p, cls, label) => (p ? `<a class="${cls}" href="${esc(hrefFor(p))}"><span class="muted small">${esc(label)}</span><b>${esc(BY_PATH[p]?.title || p)}</b></a>` : '<span></span>');
  $('#main').innerHTML = `<article class="page">
    <h1>${esc(title)}</h1>
    ${row.description ? `<p class="lead">${esc(row.description)}</p>` : ''}
    <div class="meta">
      <span class="pill trust ${esc(d.trust)}" title="${esc(t('banner.' + d.trust))}">${TRUST[d.trust] || ''} ${esc(t('trust.' + d.trust))}</span>
      ${d.confirmed && d.confirmed.by ? `<span class="small muted">${esc(t('confirmedBy'))} ${esc(d.confirmed.by)} · ${esc(String(d.confirmed.at).slice(0, 10))}</span>` : ''}
      ${d.owner === 'human' ? `<span class="small muted">${esc(t('humanOwned'))}</span>` : ''}
      <code class="file" title="${esc(d.file)}">${esc(d.file)}</code>
      <span class="actions">${ctx.extra || ''}${edit}</span>
    </div>
    ${lang && !d.exists ? `<div class="banner info">${esc(t('noTranslation', { lang: LANG_NAMES[lang] || lang }))}</div>` : ''}
    ${lang && d.exists && i18n === 'outdated' ? `<div class="banner">${esc(t('outdatedTranslation'))}</div>` : ''}
    ${d.trust === 'needs-reconfirm' ? `<div class="banner needs-reconfirm">${esc(t('banner.needs-reconfirm'))}</div>` : ''}
    ${d.fresh === 'suspect' || d.fresh === 'stale' ? `<div class="banner needs-reconfirm">${esc(t('banner.' + d.fresh))} <code>${esc([...(d.freshness?.missing || []), ...(d.freshness?.changed || [])].join(', '))}</code></div>` : ''}
    ${d.trust === 'draft' && row.space !== 'notes' ? `<div class="banner draft">${esc(t('banner.draft'))}</div>` : ''}
    ${ctx.banner || ''}
    <div id="panel"></div>
    ${d.feedback.length ? `<div class="box"><b>${esc(t('pendingComments'))}</b><ul class="list">${d.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('')}</ul></div>` : ''}
    <div id="body"></div>
    ${ctx.after || ''}
    ${d.sources.length ? `<details class="box sources"><summary><b>${esc(t('sources'))}</b> <span class="count">${d.sources.length}</span></summary>
      <ul class="list">${d.sources.map((s) => `<li><code>${esc(s)}</code></li>`).join('')}</ul></details>` : ''}
    ${i >= 0 ? `<nav class="pager">${pager(ctx.order[i - 1], 'prev', '← ' + t('prev'))}${pager(ctx.order[i + 1], 'next', t('next') + ' →')}</nav>` : ''}
  </article>`;
  CURRENT = path;
  await mountDoc($('#body'), d.exists ? d.raw : english?.exists ? english.raw : t('emptyPage'), path, anchor);
  if (STATIC) return;
  $('#a-edit').onclick = () => editDoc(d);
  $('#a-confirm')?.addEventListener('click', () => confirmPanel(d));
  $('#a-fb').onclick = () => feedbackPanel(d);
}

function confirmPanel(d) {
  $('#panel').innerHTML = `<div class="box"><b>${esc(t('confirmTitle'))}</b>
    <p class="muted">${esc(t('confirmHelp'))}</p>
    <div class="row"><input id="c-by" value="${esc(T.reviewer)}" placeholder="${esc(t('yourName'))}" style="max-width:16rem">
    <button id="c-go" type="button">${esc(t('confirm'))}</button><button id="c-x" class="ghost" type="button">${esc(t('cancel'))}</button></div></div>`;
  $('#c-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#c-go').onclick = async () => {
    await api('confirm', {}, { path: d.path, lang, by: $('#c-by').value });
    await afterChange(d.path, t('confirmedToast'));
  };
}

function feedbackPanel(d) {
  const sections = $$('#body .doc h2');               // a comment can point at one section (slug + a short quote)
  $('#panel').innerHTML = `<div class="box"><b>${esc(t('requestChange'))}</b>
    <p class="muted">${esc(t('fbHelp'))}</p>
    ${sections.length ? `<div class="row"><label class="small muted" for="f-sec">${esc(t('section'))}</label>
      <select id="f-sec"><option value="">${esc(t('wholePage'))}</option>${sections.map((h) =>
        `<option value="${esc(h.id.slice(2))}">${esc(h.dataset.title)}</option>`).join('')}</select></div>` : ''}
    <textarea id="f-text" rows="4"></textarea>
    <div class="row"><input id="f-by" value="${esc(T.reviewer)}" placeholder="${esc(t('yourName'))}" style="max-width:16rem">
    <button id="f-go" type="button">${esc(t('send'))}</button><button id="f-x" class="ghost" type="button">${esc(t('cancel'))}</button></div></div>`;
  $('#f-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#f-go').onclick = async () => {
    if (!$('#f-text').value.trim()) return;
    const slug = $('#f-sec')?.value || '';
    const heading = slug && document.getElementById('h-' + slug);
    let snippet = '';
    for (let n = heading?.nextElementSibling; n && !/^H[12]$/.test(n.tagName) && snippet.length < 80; n = n.nextElementSibling) {
      snippet += ' ' + n.textContent.trim();
    }
    await api('feedback', {}, { path: d.path, text: $('#f-text').value, by: $('#f-by').value, slug,
      snippet: snippet.trim().slice(0, 80) });
    await afterChange(d.path, t('commentSaved'));
  };
}

function editDoc(d) {
  drawToc(null);
  CURRENT = '';
  $('#main').innerHTML = `<div class="page wide"><h1>${esc(t('editing'))}: ${esc(d.title)}</h1>
    <div class="meta"><code>${esc(d.file)}</code>${lang ? ` · ${esc(t('translation'))} ${esc(lang)}` : ''}</div>
    ${d.trust === 'confirmed' ? `<div class="banner">${esc(t('confirmedWarn'))}</div>` : ''}
    <div class="editor"><textarea id="e-src" spellcheck="true"></textarea><div class="preview" id="e-prev"></div></div>
    <div class="row">
      <input id="e-msg" placeholder="${esc(t('commitMsg'))}" style="flex:1;min-width:14rem">
      <label><input type="checkbox" id="e-commit" checked> ${esc(t('commitBox'))}</label>
      <button id="e-save" type="button">${esc(t('save'))}</button><button id="e-x" class="ghost" type="button">${esc(t('cancel'))}</button>
    </div></div>`;
  const src = $('#e-src');
  src.value = d.raw || `---\ntitle: ${d.title}\n---\n\n# ${d.title}\n`;
  const preview = () => { const p = $('#e-prev'); p.innerHTML = ''; const el = render(src.value, d.path); p.append(el); drawMermaid(el); };
  let h; src.oninput = () => { clearTimeout(h); h = setTimeout(preview, 250); };
  preview();
  $('#e-x').onclick = () => route();
  $('#e-save').onclick = async () => {
    $('#e-save').disabled = true;
    try {
      await api('doc', {}, { path: d.path, lang, raw: src.value });
      if ($('#e-commit').checked) {
        const c = await api('commit', {}, { message: $('#e-msg').value || `edit ${d.path}` });
        toast(c.committed ? `${t('savedCommitted')}: ${c.head}` : t('nothingToCommit'));
      } else toast(t('saved'));
      await loadTree();
      if (location.hash === hrefFor(d.path)) route(); else location.hash = hrefFor(d.path);
    } catch (e) { toast(e.message); $('#e-save').disabled = false; }
  };
}

async function afterChange(path, msg) {
  toast(msg);
  await loadTree();
  CURRENT = '';
  await route();
}

// ---------- search and the ⌘K palette are React (src/views/Search.jsx, Palette.jsx) ----------

// ---------- review is React (src/views/Review.jsx) ----------

// ---------- the bridge: the shell (src/shell/Shell.jsx) routes, these views paint ----------
// The address table lives in src/router.js. Calls from these scripts that re-show the current address (after a save,
// a language or audience change) go back through the shell, so one view renders at a time.
function route() { return window.CamaronShell ? window.CamaronShell.go() : Promise.resolve(); }

const VIEWS = {
  showWikis: () => showWikis(), showWiki: (...a) => showWiki(...a), showWikiGraph: (...a) => showWikiGraph(...a),
  showArch: (...a) => showArch(...a), showCodeTab: (...a) => showCodeTab(...a) };

// In the app, whether this kit is a checkout with its tests (the Taller's Kit dev view).
const appInfo = () => (RUNS ? api('app/info').then((i) => { T.kitdev = i.kitdev; }, () => {}) : Promise.resolve());

window.CamaronLegacy = {
  // the docs index, the reader's language (the browser's on a first visit, when the docs are translated to it)
  async boot() {
    applyTheme();
    await loadTree();
    await appInfo();
    if (!store.get('cam-lang')) {
      const nav = (navigator.language || 'en').slice(0, 2);
      if (T.langs.includes(nav)) lang = nav;
    }
    document.documentElement.lang = lang || 'en';
  },
  async run(fn, args) {
    CURRENT = '';
    try { await VIEWS[fn](...args); } catch (e) {
      drawToc(null);
      $('#main').innerHTML = `<div class="page"><h1>${esc(t('error'))}</h1><p>${esc(e.message)}</p></div>`;
    }
  },
  leave() { CURRENT = ''; drawToc(null); document.body.classList.remove('viewer-mode', 'bare'); },
  scroll: (anchor) => scrollToAnchor(anchor),
  current: () => CURRENT,
  toast: (m) => toast(m),
  reload: () => loadTree(),
  setCurrent: (p) => { CURRENT = p; },
  // the docs renderer (doc.js), for the React doc pages until it moves to src/
  mountDoc: (el, raw, path, anchor) => mountDoc(el, raw, path, anchor),
  drawC4: (root) => drawC4(root),
  renderMd: (src, path) => render(src, path),
  drawMermaid: (el) => drawMermaid(el),
  mode: MODE,
  isStatic: () => STATIC,
  tree: () => T,
  byPath: (p) => BY_PATH[p],
  hrefFor: (p, a) => hrefFor(p, a),
  // React draws no emoji (CAMARON.md): the labels these scripts still carry lose their leading one
  t: (k, vars) => t(k, vars).replace(/^[\p{Extended_Pictographic}️‍]+\s*/u, ''),
  sectionLabel: (n) => sectionLabel(n),
  lang: () => lang,
  langName: (l) => LANG_NAMES[l] || l,
  setLang(l) { lang = l; store.set('cam-lang', l); CURRENT = ''; },
  toggleTheme() { store.set('cam-theme', isDark() ? 'light' : 'dark'); applyTheme(); CURRENT = ''; },
};

$('#zoomer').addEventListener('click', (e) => { if (e.target === $('#zoomer') || e.target.closest('#zoomer-close')) $('#zoomer').close(); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!store.get('cam-theme')) { applyTheme(); CURRENT = ''; route(); } });
