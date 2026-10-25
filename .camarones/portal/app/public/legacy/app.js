'use strict';
// The Docs space (tree, home, pages), search and review, painted into the shell's slots (#main, #toc, #tree).
// The shell (src/shell/Shell.jsx) owns the header, the sidebar's zones and the router; it calls these views through
// window.CamaronLegacy (bottom of this file) until each one moves to React.

let CURRENT = '';            // page on screen: a hash change that only moves the anchor just scrolls
let DOCS_ORDER = [];
let NOTES_ORDER = [];

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

// ---------- the Docs tree: folders in the canonical section order, working notes folded at the bottom ----------
function buildTree(rows) {
  const root = { name: '', path: '', dirs: {}, pages: [], index: null };
  for (const d of rows) {
    if (d.path === 'index.md') continue;                  // the home page
    const parts = d.path.split('/');
    let node = root;
    parts.slice(0, -1).forEach((p, i) => {
      node = node.dirs[p] ||= { name: p, path: parts.slice(0, i + 1).join('/'), dirs: {}, pages: [], index: null };
    });
    if (node !== root && parts.at(-1) === 'index.md') node.index = d; else node.pages.push(d);
  }
  return root;
}

const byTitle = (a, b) => a.title.localeCompare(b.title, lang || 'en');
function sortedDirs(node) {
  const rank = (n) => { const i = T.sections.indexOf(n); return i < 0 ? T.sections.length : i; };
  return Object.values(node.dirs).sort((a, b) => (node.path ? 0 : rank(a.name) - rank(b.name)) || a.name.localeCompare(b.name));
}

function flatten(node, out = []) {
  if (node.index) out.push(node.index.path);
  node.pages.slice().sort(byTitle).forEach((d) => out.push(d.path));
  sortedDirs(node).forEach((n) => flatten(n, out));
  return out;
}

const leaf = (d, active, label) => `<a href="${esc(hrefFor(d.path))}" class="${d.path === active ? 'on' : ''}" title="${esc(t('trust.' + d.trust))}">
  <span class="dot ${esc(d.trust)}"></span>${esc(label || d.title)}</a>`;

function drawNode(node, active) {
  const pages = node.pages.slice().sort(byTitle).map((d) => leaf(d, active)).join('');
  return pages + sortedDirs(node).map((n) => {
    if (!n.index && !Object.keys(n.dirs).length && n.pages.length === 1) return leaf(n.pages[0], active);
    const open = active.startsWith(n.path + '/');
    const label = n.index ? `<a href="${esc(hrefFor(n.index.path))}" class="${n.index.path === active ? 'on' : ''}">${esc(n.name)}</a>` : `<span>${esc(n.name)}</span>`;
    return `<details ${open ? 'open' : ''}><summary>${label}</summary><div class="sub">${drawNode(n, active)}</div></details>`;
  }).join('');
}

function drawDocsSide(active) {
  const docs = buildTree(T.docs.filter((d) => d.space === 'docs' && (!isBusiness() || forBusiness(d) || d.path === active)));
  let notes = buildTree(T.docs.filter((d) => d.space === 'notes'));
  if (!notes.pages.length && Object.keys(notes.dirs).length === 1 && notes.dirs.interview) notes = { ...notes.dirs.interview, path: '' };
  const home = BY_PATH['index.md'];
  DOCS_ORDER = [...(home ? ['index.md'] : []), ...flatten({ ...docs, dirs: {} }), ...sortedDirs(docs).flatMap((n) => flatten(n))];
  NOTES_ORDER = flatten(notes);
  $('#side-head').innerHTML = audienceSeg('side-audience') +
    (STATIC ? '' : `<a href="#/new" class="button ghost small newpage">${esc(t('newPage'))}</a>`);
  applyAudience();
  const general = docs.pages.length ? `<div class="group"><div class="group-title">${esc(t('general'))}</div>${drawNode({ ...docs, dirs: {} }, active)}</div>` : '';
  const sections = sortedDirs(docs).map((n) => {
    const title = `${SECTION_ICONS[n.name] || '📁'} ${esc(sectionLabel(n.name))}`;
    const head = n.index ? `<a class="group-title ${n.index.path === active ? 'on' : ''}" href="${esc(hrefFor(n.index.path))}">${title}</a>`
      : `<div class="group-title">${title}</div>`;
    return `<div class="group">${head}${drawNode({ ...n, index: null }, active)}</div>`;
  }).join('');
  const notesOpen = BY_PATH[active]?.space === 'notes';
  $('#tree').innerHTML = `<div class="group"><a href="#/docs" class="${!active ? 'on' : ''}">🏠 ${esc(t('docsHome'))}</a></div>${general}${sections}
    ${NOTES_ORDER.length ? `<details class="notes" ${notesOpen ? 'open' : ''}><summary>🗒️ ${esc(t('notes'))} <span class="count">${NOTES_ORDER.length}</span></summary>
      <p class="muted small">${esc(t('notesHelp'))}</p><div class="sub">${drawNode(notes, active)}</div></details>` : ''}`;
  $('#tree .on')?.scrollIntoView({ block: 'nearest' });
}

// ---------- Home and the zones are React (src/views/Home.jsx, the shell's sidebar) ----------
// The project has nothing of its own yet (the kit's guides and interview notes do not count).
function emptyProject() {
  const kit = new Set(T.kitGuides || []);
  return !T.docs.some((d) => d.space === 'docs' && !kit.has(d.path) && d.type !== 'interview') && !T.views.length;
}

// ---------- the Docs zone's cover (#/docs): sections, C4, wikis and the project's index page ----------
async function showDocsHome() {
  drawChrome('docs');
  drawDocsSide('');
  CURRENT = '';
  const docs = T.docs.filter((d) => d.space === 'docs' && (!isBusiness() || forBusiness(d)));
  const wikiPages = isBusiness() ? 0 : T.docs.filter((d) => d.space === 'wiki').length;
  if (emptyProject()) return location.replace('#/');      // Home offers the first look
  const home = BY_PATH['index.md'];
  const tree = buildTree(docs);
  const confirmed = docs.length ? Math.round(100 * docs.filter((d) => d.trust === 'confirmed').length / docs.length) : 0;
  const flows = T.views.filter((v) => v.kind === 'dynamic').length || (tree.dirs.flows ? tree.dirs.flows.pages.length : 0);
  const stats = [t('statPages', { n: docs.length }), t('statConfirmed', { n: confirmed }),
    flows ? t('statFlows', { n: flows }) : '', T.views.length ? t('statViews', { n: T.views.length }) : ''].filter(Boolean);
  const card = (href, icon, label, desc, count) => `<a class="card link" href="${esc(href)}"><div class="card-icon">${icon}</div>
    <div><b>${esc(label)}</b>${count ? ` <span class="count">${count}</span>` : ''}<p class="muted small">${esc(desc)}</p></div></a>`;
  const cards = sortedDirs(tree).map((n) => {
    const first = n.index?.path || flatten(n)[0];
    return card(hrefFor(first), SECTION_ICONS[n.name] || '📁', sectionLabel(n.name), has('secd.' + n.name) ? t('secd.' + n.name) : '', flatten(n).length);
  });
  if (T.views.length) cards.splice(1, 0, card('#/c4', '🗺️', 'C4', t('secd.c4'), T.views.length));
  if (wikiPages) cards.push(card('#/wikis', '📚', t('wikis'), t('secd.wikis'), wikiPages));
  const context = T.views.some((v) => v.id === 'index');
  $('#main').innerHTML = `<div class="page wide home">
    <header class="hero"><h1>${esc(home?.title && home.title !== 'index' ? home.title : T.project)}</h1>
      <p class="lead">${esc(home?.description || t('homeLead'))}</p>
      <div class="stats">${stats.map((s) => `<span class="pill">${esc(s)}</span>`).join('')}</div>
      ${STATIC ? '' : `<form class="home-ask" id="home-ask"><input name="q" placeholder="${esc(t('homeAskPh'))}"
        aria-label="${esc(t('homeAsk'))}" autocomplete="off"><button type="submit">${esc(t('homeAsk'))}</button></form>`}
      ${isBusiness() ? `<p class="muted small">${esc(t('businessOn'))}</p>` : ''}</header>
    <div class="cards">${cards.join('')}</div>
    ${context ? `<h2 class="home-h">${esc(t('systemContext'))}</h2><div class="c4embed" data-view="index"></div>` : ''}
    <div id="body"></div></div>`;
  drawToc(null);
  $('#home-ask')?.addEventListener('submit', (e) => {
    e.preventDefault();
    const q = e.target.q.value.trim();
    if (q) location.hash = `#/ask/${encodeURIComponent(q)}`;
  });
  const tasks = [drawC4($('#main'))];
  if (home) {
    const d = await api('doc', { path: 'index.md', lang });
    const raw = d.exists ? d.raw : (await api('doc', { path: 'index.md' })).raw;
    tasks.push(mountDoc($('#body'), raw, 'index.md'));
  }
  await Promise.all(tasks);
}

// ---------- pages (their breadcrumbs are in the top bar: drawChrome) ----------
async function showDoc(path, anchor) {
  drawChrome('docs');
  drawDocsSide(path);
  const notes = BY_PATH[path]?.space === 'notes';
  await showPage(path, anchor, { order: notes ? NOTES_ORDER : DOCS_ORDER });
}

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

function newPage() {
  drawChrome('docs');
  drawDocsSide('');
  drawToc(null);
  $('#main').innerHTML = `<div class="page"><h1>${esc(t('newPage').replace('+ ', ''))}</h1><div class="box">
    <input id="n-title" placeholder="${esc(t('newTitle'))}">
    <div class="row"><input id="n-path" placeholder="${esc(t('newPath'))}"></div>
    <div class="row"><button id="n-go" type="button">${esc(t('create'))}</button></div></div></div>`;
  $('#n-title').oninput = () => { $('#n-path').value = 'guides/' + $('#n-title').value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'; };
  $('#n-go').onclick = async () => {
    try {
      const d = await api('new', {}, { path: $('#n-path').value, title: $('#n-title').value });
      await loadTree();
      history.replaceState(null, '', hrefFor(d.path));
      editDoc(d);
    } catch (e) { toast(e.message); }
  };
}

// ---------- search and the ⌘K palette are React (src/views/Search.jsx, Palette.jsx) ----------

// ---------- review is React (src/views/Review.jsx) ----------

// ---------- the bridge: the shell (src/shell/Shell.jsx) routes, these views paint ----------
// The address table lives in src/router.js. Calls from these scripts that re-show the current address (after a save,
// a language or audience change) go back through the shell, so one view renders at a time.
function route() { return window.CamaronShell ? window.CamaronShell.go() : Promise.resolve(); }

const VIEWS = { showDocsHome, showDoc, newPage,
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
  docsOrder: () => DOCS_ORDER,
  mode: MODE,
  isStatic: () => STATIC,
  tree: () => T,
  byPath: (p) => BY_PATH[p],
  hrefFor: (p, a) => hrefFor(p, a),
  t: (k, vars) => t(k, vars),
  sectionLabel: (n) => sectionLabel(n),
  lang: () => lang,
  langName: (l) => LANG_NAMES[l] || l,
  setLang(l) { lang = l; store.set('cam-lang', l); CURRENT = ''; },
  toggleTheme() { store.set('cam-theme', isDark() ? 'light' : 'dark'); applyTheme(); CURRENT = ''; },
};

$('#zoomer').addEventListener('click', (e) => { if (e.target === $('#zoomer') || e.target.closest('#zoomer-close')) $('#zoomer').close(); });
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!store.get('cam-theme')) { applyTheme(); CURRENT = ''; route(); } });
