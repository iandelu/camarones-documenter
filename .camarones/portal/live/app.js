'use strict';
// Chrome, the Docs space (tree, home, pages), search, review and routing.

let CURRENT = '';            // page on screen: a hash change that only moves the anchor just scrolls
let DOCS_ORDER = [];
let NOTES_ORDER = [];

function drawChrome(active, { viewer = false, bare = false } = {}) {
  document.documentElement.lang = lang || 'en';
  const wikis = !STATIC || T.docs.some((d) => d.space === 'wiki');
  const tabs = [['docs', '#/'], ['c4', '#/c4'], ...(wikis ? [['wikis', '#/wikis']] : []), ['review', '#/review']];
  $('#tabs').innerHTML = tabs.map(([k, href]) => `<a href="${href}" class="${k === active ? 'on' : ''}">${esc(t(k))}</a>`).join('');
  $('#search-label').textContent = t('search');
  $('#theme').title = t('theme');
  $('#menu').title = t('menu');
  $('#ro').hidden = !STATIC;
  $('#ro').innerHTML = t('readOnly');
  const langs = ['', ...T.langs];
  $('#lang').hidden = langs.length < 2;
  $('#lang').innerHTML = langs.map((l) => `<option value="${l}">${esc(LANG_NAMES[l || 'en'] || l)}</option>`).join('');
  $('#lang').value = langs.includes(lang) ? lang : '';
  document.body.classList.toggle('viewer-mode', viewer);
  document.body.classList.toggle('bare', bare);
  document.body.classList.remove('nav-open');
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
  const docs = buildTree(T.docs.filter((d) => d.space === 'docs'));
  let notes = buildTree(T.docs.filter((d) => d.space === 'notes'));
  if (!notes.pages.length && Object.keys(notes.dirs).length === 1 && notes.dirs.interview) notes = { ...notes.dirs.interview, path: '' };
  const home = BY_PATH['index.md'];
  DOCS_ORDER = [...(home ? ['index.md'] : []), ...flatten({ ...docs, dirs: {} }), ...sortedDirs(docs).flatMap((n) => flatten(n))];
  NOTES_ORDER = flatten(notes);
  $('#side-head').innerHTML = STATIC ? '' : `<a href="#/new" class="button ghost small newpage">${esc(t('newPage'))}</a>`;
  const general = docs.pages.length ? `<div class="group"><div class="group-title">${esc(t('general'))}</div>${drawNode({ ...docs, dirs: {} }, active)}</div>` : '';
  const sections = sortedDirs(docs).map((n) => {
    const title = `${SECTION_ICONS[n.name] || '📁'} ${esc(sectionLabel(n.name))}`;
    const head = n.index ? `<a class="group-title ${n.index.path === active ? 'on' : ''}" href="${esc(hrefFor(n.index.path))}">${title}</a>`
      : `<div class="group-title">${title}</div>`;
    return `<div class="group">${head}${drawNode({ ...n, index: null }, active)}</div>`;
  }).join('');
  const notesOpen = BY_PATH[active]?.space === 'notes';
  $('#tree').innerHTML = `<div class="group"><a href="#/" class="${!active ? 'on' : ''}">🏠 ${esc(t('home'))}</a></div>${general}${sections}
    ${NOTES_ORDER.length ? `<details class="notes" ${notesOpen ? 'open' : ''}><summary>🗒️ ${esc(t('notes'))} <span class="count">${NOTES_ORDER.length}</span></summary>
      <p class="muted small">${esc(t('notesHelp'))}</p><div class="sub">${drawNode(notes, active)}</div></details>` : ''}`;
  $('#tree .on')?.scrollIntoView({ block: 'nearest' });
}

// ---------- home ----------
async function showHome() {
  drawChrome('docs');
  drawDocsSide('');
  CURRENT = '';
  const docs = T.docs.filter((d) => d.space === 'docs');
  const wikiPages = T.docs.filter((d) => d.space === 'wiki').length;
  if (!docs.length && !T.views.length) {
    drawToc(null);
    $('#main').innerHTML = `<div class="page hero empty"><div class="hero-logo">🦐</div><h1>${esc(T.project)}</h1>
      <p class="lead">${esc(t('homeEmpty'))}</p><p class="muted">${esc(t('noDocsHelp'))}</p></div>`;
    return;
  }
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
      <div class="stats">${stats.map((s) => `<span class="pill">${esc(s)}</span>`).join('')}</div></header>
    <div class="cards">${cards.join('')}</div>
    ${context ? `<h2 class="home-h">${esc(t('systemContext'))}</h2><div class="c4embed" data-view="index"></div>` : ''}
    <div id="body"></div></div>`;
  drawToc(null);
  const tasks = [drawC4($('#main'))];
  if (home) {
    const d = await api('doc', { path: 'index.md', lang });
    const raw = d.exists ? d.raw : (await api('doc', { path: 'index.md' })).raw;
    tasks.push(mountDoc($('#body'), raw, 'index.md'));
  }
  await Promise.all(tasks);
}

// ---------- pages ----------
function crumbsFor(path) {
  const row = BY_PATH[path] || {};
  const parts = path.split('/').slice(0, -1);
  const out = [['#/', t('home')]];
  if (row.space === 'notes') out.push(['', t('notes')]);
  parts.forEach((p, i) => {
    const idx = parts.slice(0, i + 1).join('/') + '/index.md';
    const label = i === 0 && row.space !== 'notes' ? sectionLabel(p) : p;
    out.push([BY_PATH[idx] && idx !== path ? hrefFor(idx) : '', label]);
  });
  return out;
}

async function showDoc(path, anchor) {
  drawChrome('docs');
  drawDocsSide(path);
  const notes = BY_PATH[path]?.space === 'notes';
  await showPage(path, anchor, { crumbs: crumbsFor(path), order: notes ? NOTES_ORDER : DOCS_ORDER });
}

async function showPage(path, anchor, ctx) {
  const d = await api('doc', { path, lang });
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
    <nav class="crumbs">${ctx.crumbs.map(([h, l]) => (h ? `<a href="${esc(h)}">${esc(l)}</a>` : `<span>${esc(l)}</span>`)).join('<span class="sep">›</span>')}</nav>
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
    ${d.trust === 'draft' && row.space !== 'notes' ? `<div class="banner draft">${esc(t('banner.draft'))}</div>` : ''}
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
  $('#panel').innerHTML = `<div class="box"><b>${esc(t('requestChange'))}</b>
    <p class="muted">${esc(t('fbHelp'))}</p>
    <textarea id="f-text" rows="4"></textarea>
    <div class="row"><input id="f-by" value="${esc(T.reviewer)}" placeholder="${esc(t('yourName'))}" style="max-width:16rem">
    <button id="f-go" type="button">${esc(t('send'))}</button><button id="f-x" class="ghost" type="button">${esc(t('cancel'))}</button></div></div>`;
  $('#f-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#f-go').onclick = async () => {
    if (!$('#f-text').value.trim()) return;
    await api('feedback', {}, { path: d.path, text: $('#f-text').value, by: $('#f-by').value });
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

// ---------- search: ⌘K palette (titles instantly, full text as you type) and a full results page ----------
const SPACE_ICON = { docs: '📄', wiki: '📚', notes: '🗒️' };
const markTerms = (s, q) => { let h = esc(s); for (const w of q.match(/\w{2,}/g) || []) h = h.replace(new RegExp(`(${w})`, 'gi'), '<mark>$1</mark>'); return h; };
const spaceRank = (p) => ({ docs: 0, wiki: 1, notes: 2 }[BY_PATH[p]?.space] ?? 3);

async function showSearch(q) {
  drawChrome('docs');
  drawDocsSide('');
  drawToc(null);
  CURRENT = '';
  const hits = (await api('search', { q })).slice().sort((a, b) => spaceRank(a.path) - spaceRank(b.path) || b.score - a.score);
  $('#main').innerHTML = `<div class="page"><h1>${esc(t('results'))} “${esc(q)}”</h1>` + (hits.map((h) =>
    `<div class="hit"><a href="${esc(hrefFor(h.path))}">${SPACE_ICON[BY_PATH[h.path]?.space] || '📄'} ${esc(h.title)}</a>
     <span class="muted small">${esc(h.path)}</span>
     ${h.lines.map((l) => `<div class="snip">${markTerms(l, q)}</div>`).join('')}</div>`).join('') || `<p class="muted">${esc(t('noResults'))}</p>`) + '</div>';
}

const PAL = { items: [], sel: 0, timer: 0, seq: 0 };
function openPalette() {
  const dlg = $('#palette');
  if (dlg.open) return;
  $('#pal-q').placeholder = t('searchPh');
  $('#pal-hint').textContent = t('searchHint');
  $('#pal-q').value = '';
  dlg.showModal();
  $('#pal-q').focus();
  paletteInput();
}

function paletteDraw(groups) {
  PAL.items = groups.flatMap(([, items]) => items);
  PAL.sel = Math.min(PAL.sel, Math.max(PAL.items.length - 1, 0));
  let n = 0;
  $('#pal-list').innerHTML = groups.filter(([, items]) => items.length).map(([label, items]) => `<div class="pal-group">${esc(label)}</div>` +
    items.map((it) => `<a class="pal-item ${n++ === PAL.sel ? 'on' : ''}" href="${esc(it.href)}">${it.icon} <span><b>${it.title}</b>
      ${it.sub ? `<span class="muted small">${it.sub}</span>` : ''}</span></a>`).join('')).join('')
    || (PAL.q ? `<p class="muted pal-empty">${esc(t('noMatch'))}</p>` : '');
  $('#pal-list .on')?.scrollIntoView({ block: 'nearest' });
}

function paletteInput() {
  const q = $('#pal-q').value.trim();
  PAL.q = q;
  PAL.sel = 0;
  const low = q.toLowerCase();
  const item = (d, sub) => ({ href: hrefFor(d.path), icon: SPACE_ICON[d.space] || '📄', title: q ? markTerms(d.title, q) : esc(d.title),
    sub: sub ?? esc(d.space === 'notes' ? `${d.path} · ${t('inNotes')}` : d.path) });
  const titles = (q ? T.docs.filter((d) => (d.title + ' ' + d.path).toLowerCase().includes(low))
    : DOCS_ORDER.map((p) => BY_PATH[p]).filter(Boolean)).sort((a, b) => (q ? spaceRank(a.path) - spaceRank(b.path) : 0)).slice(0, 8);
  const groups = [[t('titles'), titles.map((d) => item(d))]];
  paletteDraw(groups);
  clearTimeout(PAL.timer);
  if (q.length < 2) return;
  const seq = ++PAL.seq;
  PAL.timer = setTimeout(async () => {
    try {
      const seen = new Set(titles.map((d) => d.path));
      const hits = (await api('search', { q })).filter((h) => !seen.has(h.path) && BY_PATH[h.path])
        .sort((a, b) => spaceRank(a.path) - spaceRank(b.path)).slice(0, 8);
      if (seq !== PAL.seq) return;
      const content = hits.map((h) => item(BY_PATH[h.path], h.lines[0] ? markTerms(h.lines[0].slice(0, 140), q) : ''));
      content.push({ href: `#/search/${encodeURIComponent(q)}`, icon: '🔎', title: esc(t('searchAll', { q })), sub: '' });
      paletteDraw([...groups, [t('content'), content]]);
    } catch { /* keep the title matches */ }
  }, 180);
}

function paletteKey(e) {
  if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
    e.preventDefault();
    const n = PAL.items.length;
    if (!n) return;
    PAL.sel = (PAL.sel + (e.key === 'ArrowDown' ? 1 : n - 1)) % n;
    $$('#pal-list .pal-item').forEach((a, i) => a.classList.toggle('on', i === PAL.sel));
    $('#pal-list .on')?.scrollIntoView({ block: 'nearest' });
  } else if (e.key === 'Enter') {
    e.preventDefault();
    const it = PAL.items[PAL.sel];
    const q = $('#pal-q').value.trim();
    if (it) location.hash = it.href; else if (q) location.hash = `#/search/${encodeURIComponent(q)}`;
    $('#palette').close();
  }
}

// ---------- review ----------
async function showReview() {
  drawChrome('review');
  drawDocsSide('');
  drawToc(null);
  CURRENT = '';
  const s = await api('status');
  const changed = Object.entries(s.changes).filter(([, c]) => c.status !== 'up-to-date');
  $('#main').innerHTML = `<div class="page"><h1>${esc(t('reviewTitle'))}</h1>
    <p class="muted">${esc(t('planUnits', { done: s.plan.done, total: s.plan.total, pages: T.summary.total }))} · ${esc($('#summary').textContent)}</p>
    <div class="box"><b>${esc(t('waiting'))} (${s.queue.length})</b><ul class="list">${s.queue.map((r) =>
      `<li>${TRUST[r.trust]} <a href="${esc(hrefFor(r.path))}">${esc(r.title)}</a> <span class="muted small">${esc(r.path)}</span></li>`).join('') || `<li class="muted">${esc(t('allConfirmed'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('changeRequests'))} (${s.feedback.length})</b><ul class="list">${s.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('') || `<li class="muted">${esc(t('none'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('codeChanged'))} (${changed.length})</b><ul class="list">${changed.map(([n, c]) =>
      `<li><b>${esc(n)}</b> — ${esc(c.status)}${c.files ? ` (${c.files.length} ${esc(t('files'))})` : ''}</li>`).join('') || `<li class="muted">${esc(t('allDocumented'))}</li>`}</ul>
      <p class="muted small">${esc(t('askAgent'))}</p></div>
    <div class="box"><b>${esc(t('checks'))}</b><ul class="list">${[...s.check.errors.map((e) => `<li>❌ ${esc(e)}</li>`), ...s.check.warnings.map((w) => `<li>⚠️ ${esc(w)}</li>`)].join('') || `<li class="muted">${esc(t('allPass'))}</li>`}</ul></div></div>`;
}

// ---------- routing (old links keep working: #/docs/repos/<repo>/<wiki page>, #/wikis/<repo>, #/code/<repo>) ----------
// One view renders at a time and a newer hash skips the queued ones, so a slow page never paints over the next.
let routing = Promise.resolve();
let routeSeq = 0;
function route() {
  const seq = ++routeSeq;
  routing = routing.then(() => (seq === routeSeq ? routeNow() : undefined));
  return routing;
}

async function routeNow() {
  const h = decodeURIComponent(location.hash.slice(1));
  const [, view = '', rest = ''] = h.match(/^\/([\w-]*)\/?(.*)$/) || [];
  if ($('#palette').open) $('#palette').close();
  try {
    if (view === 'docs' || view === 'doc') {
      if (!rest) return await showHome();
      const [path, anchor] = rest.split('::');
      if (BY_PATH[path]?.space === 'wiki') return location.replace(hrefFor(path, anchor));
      if (path === CURRENT && anchor !== undefined && $('#body')) return scrollToAnchor(anchor);
      return await showDoc(path, anchor);
    }
    if (view === 'wiki') {
      const [repo = '', ...more] = rest.split('/');
      const [rel = '', anchor] = more.join('/').split('::');
      if (rel && `repos/${repo}/${rel}` === CURRENT && anchor !== undefined && $('#body')) return scrollToAnchor(anchor);
      CURRENT = '';
      if (!repo) return await showWikis();
      return rel ? await showWiki(repo, rel, anchor) : await showWikiGraph(repo);
    }
    CURRENT = '';
    if (view === 'wikis') return rest ? location.replace(`#/wiki/${rest}`) : await showWikis();
    if (view === 'c4') return await showArch(rest);
    if (view === 'code') return location.replace(`#/c4/code${rest ? '/' + rest : ''}`);
    if (view === 'review' || view === 'status') return await showReview();
    if (view === 'search') return await showSearch(rest);
    if (view === 'new' && !STATIC) return newPage();
    return await showHome();
  } catch (e) {
    drawToc(null);
    $('#main').innerHTML = `<div class="page"><h1>${esc(t('error'))}</h1><p>${esc(e.message)}</p></div>`;
  }
}

$('#lang').onchange = (e) => { lang = e.target.value; store.set('cam-lang', lang); CURRENT = ''; route(); };
$('#theme').onclick = () => { store.set('cam-theme', isDark() ? 'light' : 'dark'); applyTheme(); CURRENT = ''; route(); };
matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!store.get('cam-theme')) { applyTheme(); CURRENT = ''; route(); } });
$('#menu').onclick = () => document.body.classList.toggle('nav-open');
$('#scrim').onclick = () => document.body.classList.remove('nav-open');
$('#search-btn').onclick = openPalette;
$('#pal-q').oninput = paletteInput;
$('#pal-q').onkeydown = paletteKey;
$('#palette').addEventListener('click', (e) => { if (e.target === $('#palette')) $('#palette').close(); });
$('#zoomer').addEventListener('click', (e) => { if (e.target === $('#zoomer') || e.target.closest('#zoomer-close')) $('#zoomer').close(); });
document.addEventListener('keydown', (e) => {
  const typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement?.tagName || '');
  if ((e.key === 'k' && (e.metaKey || e.ctrlKey)) || (e.key === '/' && !typing)) { e.preventDefault(); openPalette(); }
});
addEventListener('hashchange', route);
applyTheme();
$('#search-key').textContent = /Mac|iPhone|iPad/.test(navigator.platform) ? '⌘K' : 'Ctrl K';
loadTree().then(() => {
  if (!store.get('cam-lang')) {           // first visit: the browser's language when the docs are translated to it
    const nav = (navigator.language || 'en').slice(0, 2);
    if (T.langs.includes(nav)) lang = nav;
  }
  return route();
}).catch((e) => { drawChrome('docs'); $('#main').innerHTML = `<div class="page"><h1>${esc(t('unreachable'))}</h1><p>${esc(e.message)}</p></div>`; });
