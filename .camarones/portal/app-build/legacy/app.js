'use strict';
// Chrome, the Docs space (tree, home, pages), search, review and routing.

let CURRENT = '';            // page on screen: a hash change that only moves the anchor just scrolls
let DOCS_ORDER = [];
let NOTES_ORDER = [];

// The React views need the live server; the zones (src/zones.js) know what each mode has. `app`: the desktop app's
// window, which also has the Taller (machine work).
const MODE = () => (STATIC || !window.CamaronNative ? 'static' : RUNS ? 'app' : 'live');
const TALLER = ['generate', 'analyze', 'check', 'interviews', 'team', 'machine', 'kitdev'];

// Where the reader is, from the address: camarón / zone / view / page. No tab bar: Home tiles, zone covers and ⌘K
// reach every view. `active` is kept for callers; the address alone decides the crumbs.
function drawChrome(active, { viewer = false, bare = false, nativeView = false } = {}) {
  document.documentElement.lang = lang || 'en';
  const crumbs = window.CamaronZones?.crumbs(location.hash, MODE(), T) || [];   // none if the bundle did not load
  $('#crumbs').innerHTML = crumbs.map((c, i) => {
    const label = esc(!c.key ? c.text : c.key.startsWith('sec.') ? sectionLabel(c.key.slice(4)) : t(c.key));
    const last = i === crumbs.length - 1;
    const item = c.href && !last ? `<a href="${esc(c.href)}">${label}</a>` : `<span${last ? ' aria-current="page"' : ''}>${label}</span>`;
    return `<span class="sep" aria-hidden="true">/</span>${item}`;
  }).join('');
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
  document.body.classList.toggle('native-mode', nativeView);
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

// ---------- Home (#/): ask first, then the project's state, then the zones ----------
const homeTile = (href, title, desc) => `<a class="home-tile" href="${esc(href)}"><b>${esc(title)}</b><p>${esc(desc)}</p></a>`;

// The project has nothing of its own yet (the kit's guides and interview notes do not count).
function emptyProject() {
  const kit = new Set(T.kitGuides || []);
  return !T.docs.some((d) => d.space === 'docs' && !kit.has(d.path) && d.type !== 'interview') && !T.views.length;
}

// One way forward instead of empty tiles: a first look from the code (no AI), or the tutorial.
function drawEmptyProject() {
  drawToc(null);
  $('#main').innerHTML = `<div class="page hero empty aurora-bg"><div class="hero-logo">🦐</div><h1>${esc(T.project)}</h1>
    <p class="lead">${esc(t('homeEmpty'))}</p><p class="muted">${esc(t('noDocsHelp'))}</p>
    ${STATIC ? '' : `<div class="row center">${RUNS ? `<button id="first-look" type="button">${esc(t('firstLook'))}</button>` : ''}
      <a class="button ghost" href="#/pipeline">${esc(t('nextUnit'))} →</a></div><pre id="first-log" class="joblog" hidden></pre>
      ${RUNS ? '' : `<p class="aviso small">${esc(t('appOnly'))}</p>`}`}
    ${T.kitGuides?.length ? `<p class="small"><a href="${esc(hrefFor(T.kitGuides.find((g) => g.endsWith('tutorial.md')) || T.kitGuides[0]))}">📘 ${esc(t('readTutorial'))}</a></p>` : ''}</div>`;
  $('#first-look')?.addEventListener('click', (e) => startBuild('first-look', '', e.target, $('#first-log'), () => location.reload()));
}

async function showStart() {
  drawChrome('home', { bare: true });
  CURRENT = '';
  drawToc(null);
  if (emptyProject()) return drawEmptyProject();
  const Z = window.CamaronZones;
  if (!Z) return showDocsHome();           // the bundle did not load: the docs home still works without it
  const kpis = Z.homeKpis(T);
  const askLabel = t(STATIC ? 'search' : 'homeAsk');
  $('#main').innerHTML = `<div class="page wide start">
    <header class="start-hero aurora-bg">
      <p class="eyebrow">${esc(t('home.eyebrow', { project: T.project, n: T.repos.length }))}</p>
      <h1 class="t-impact">${esc(t('home.title'))}<br><span class="t-eco">${esc(t('home.eco'))}</span></h1>
      <form class="start-ask" id="start-ask"><input name="q" placeholder="${esc(t('home.askPh'))}" aria-label="${esc(askLabel)}"
        autocomplete="off"><button type="submit">${esc(askLabel)} <span aria-hidden="true">→</span></button></form>
    </header>
    ${kpis.length ? `<section class="start-sec"><div class="start-h"><h2 class="t-impact">${esc(t('home.state'))}</h2>
      <span class="eyebrow">${esc(t('home.stateSub'))}</span></div>
      <div class="home-kpis">${kpis.map((k) => `<div class="home-kpi ${k.tone || ''}"><span class="eyebrow">${esc(t('kpi.' + k.id))}</span>
        <b>${esc(k.value)}</b><small>${esc(t('kpid.' + k.id))}</small></div>`).join('')}</div></section>` : ''}
    <section class="start-sec"><div class="start-h"><h2 class="t-impact">${esc(t('home.zones'))}</h2></div>
      <div class="home-tiles">${Z.zonesFor(MODE(), T).map((z) => homeTile(z.href, t('zone.' + z.id), t('zoned.' + z.id))).join('')}</div></section>
  </div>`;
  $('#start-ask').addEventListener('submit', (e) => {
    e.preventDefault();
    const q = e.target.q.value.trim();
    if (q) location.hash = `${STATIC ? '#/search/' : '#/ask/'}${encodeURIComponent(q)}`;
  });
}

// A zone's cover (#/arch, #/plan, #/quality): its title and one tile per view this mode has.
function showZone(id) {
  if (!window.CamaronZones) return location.replace('#/docs');
  const zone = window.CamaronZones.zonesFor(MODE(), T).find((z) => z.id === id);
  if (!zone) return location.replace('#/');
  drawChrome(id, { bare: true });
  CURRENT = '';
  drawToc(null);
  $('#main').innerHTML = `<div class="page wide start"><header class="start-head">
    <h1 class="t-impact">${esc(t('zone.' + id))}<br><span class="t-eco">${esc(t('zoned.' + id))}</span></h1></header>
    <div class="home-tiles">${zone.views.map((v) => homeTile(v.href, t('view.' + v.id), t('viewd.' + v.id))).join('')}</div></div>`;
}

// ---------- the Docs zone's cover (#/docs): sections, C4, wikis and the project's index page ----------
async function showDocsHome() {
  drawChrome('docs');
  drawDocsSide('');
  CURRENT = '';
  const docs = T.docs.filter((d) => d.space === 'docs' && (!isBusiness() || forBusiness(d)));
  const wikiPages = isBusiness() ? 0 : T.docs.filter((d) => d.space === 'wiki').length;
  if (emptyProject()) return drawEmptyProject();
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
  await mountDoc($('#body'), d.exists ? d.raw : english?.exists ? english.raw : t('emptyPage'), path, anchor, d.exists ? d.blocks : []);
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
        `<option value="${esc(h.id.slice(2))}">${esc(h.dataset.title)}</option>`).join('')}</select>
      <button id="f-item" class="ghost small" type="button" title="${esc(t('createItemHint'))}">${esc(t('createItem'))} →</button></div>`
      : `<div class="row"><button id="f-item" class="ghost small" type="button" title="${esc(t('createItemHint'))}">${esc(t('createItem'))} →</button></div>`}
    <textarea id="f-text" rows="4"></textarea>
    <div class="row"><input id="f-by" value="${esc(T.reviewer)}" placeholder="${esc(t('yourName'))}" style="max-width:16rem">
    <button id="f-go" type="button">${esc(t('send'))}</button><button id="f-x" class="ghost" type="button">${esc(t('cancel'))}</button></div></div>`;
  $('#f-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#f-item').onclick = async () => {       // the Board's add form, with a link to this page (and section) filled in
    let slug = $('#f-sec')?.value || '';
    if (slug && lang && d.exists) {           // a translation: links point at the source page, the same H2 by position
      const i = sections.findIndex((h) => h.id === 'h-' + slug);
      const src = await api('doc', { path: d.path });
      slug = ($$('h2', render(src.raw || '', d.path))[i]?.id || '').slice(2);
    }
    location.hash = `#/kanban/new?path=${encodeURIComponent(d.path)}${slug ? `&section=${encodeURIComponent(slug)}` : ''}`;
  };
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

// ---------- search: ⌘K palette (titles instantly, full text as you type) and a full results page ----------
const SPACE_ICON = { docs: '📄', wiki: '📚', notes: '🗒️' };
const markTerms = (s, q) => { let h = esc(s); for (const w of q.match(/\w{2,}/g) || []) h = h.replace(new RegExp(`(${w})`, 'gi'), '<mark>$1</mark>'); return h; };
const spaceRank = (p) => ({ docs: 0, wiki: 1, notes: 2 }[BY_PATH[p]?.space] ?? 3);

async function showSearch(q) {
  drawChrome('docs');
  drawDocsSide('');
  drawToc(null);
  CURRENT = '';
  const hits = (await api('search', { q, track: 1 })).slice().sort((a, b) => spaceRank(a.path) - spaceRank(b.path) || b.score - a.score);
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
  const places = (window.CamaronZones?.paletteEntries(MODE(), T) || [])     // zones and views: "libr" → Libraries
    .map((e) => ({ ...e, label: t(e.key), where: e.key.startsWith('view.') ? t('zone.' + e.zone) : '' }))
    .filter((e) => !q || `${e.label} ${e.where}`.toLowerCase().includes(low)).slice(0, 8)
    .map((e) => ({ href: e.href, icon: '<span aria-hidden="true">→</span>', title: q ? markTerms(e.label, q) : esc(e.label), sub: esc(e.where) }));
  const groups = [[t('zonesGroup'), places], [t('titles'), titles.map((d) => item(d))]];
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
  const requests = STATIC ? [] : await api('reviews').catch(() => []);
  const changed = Object.entries(s.changes).filter(([, c]) => c.status !== 'up-to-date');
  $('#main').innerHTML = `<div class="page"><h1>${esc(t('reviewTitle'))}</h1>
    <p class="muted">${esc(t('planUnits', { done: s.plan.done, total: s.plan.total, pages: T.summary.total }))} · ${esc($('#summary').textContent)}</p>
    ${requests.length ? `<div class="box"><b>${esc(t('reviewRequests'))} (${requests.length})</b><ul class="list">${requests.map((r) =>
      `<li class="rv" data-id="${esc(r.id)}"><a href="${esc(hrefFor(r.path))}">${esc(BY_PATH[r.path]?.title || r.path)}</a>
        <span class="muted small">${esc(r.by)}${r.note ? ' · ' + esc(r.note) : ''}</span>
        <div class="row"><button class="small rv-ok" type="button">${esc(t('approve'))}</button>
          <input class="rv-text" placeholder="${esc(t('whatChanges'))}" style="flex:1;min-width:12rem">
          <button class="ghost small rv-no" type="button">${esc(t('askChanges'))}</button></div></li>`).join('')}</ul></div>` : ''}
    <div class="box"><b>${esc(t('waiting'))} (${s.queue.length})</b><ul class="list">${s.queue.map((r) =>
      `<li>${TRUST[r.trust]} <a href="${esc(hrefFor(r.path))}">${esc(r.title)}</a> <span class="muted small">${esc(r.path)}</span></li>`).join('') || `<li class="muted">${esc(t('allConfirmed'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('changeRequests'))} (${s.feedback.length})</b><ul class="list">${s.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('') || `<li class="muted">${esc(t('none'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('codeChanged'))} (${changed.length})</b><ul class="list">${changed.map(([n, c]) =>
      `<li><b>${esc(n)}</b> — ${esc(c.status)}${c.files ? ` (${c.files.length} ${esc(t('files'))})` : ''}</li>`).join('') || `<li class="muted">${esc(t('allDocumented'))}</li>`}</ul>
      <p class="muted small">${esc(t('askAgent'))}</p></div>
    <div class="box"><b>${esc(t('checks'))}</b><ul class="list">${[...s.check.errors.map((e) => `<li>❌ ${esc(e)}</li>`), ...s.check.warnings.map((w) => `<li>⚠️ ${esc(w)}</li>`)].join('') || `<li class="muted">${esc(t('allPass'))}</li>`}</ul></div></div>`;
  $$('#main .rv').forEach((li) => {
    const send = async (decision) => {
      const comments = $('.rv-text', li).value.trim();
      if (decision === 'changes' && !comments) { $('.rv-text', li).focus(); return; }
      await api('review/decide', {}, { id: li.dataset.id, decision, comments, by: T.reviewer });
      toast(t('decided'));
      showReview();
    };
    $('.rv-ok', li).onclick = () => send('approve');
    $('.rv-no', li).onclick = () => send('changes');
  });
}

// ---------- routing (old links keep working: #/docs/repos/<repo>/<wiki page>, #/wikis/<repo>, #/c4/code/<repo>) ----------
// One view renders at a time and a newer hash skips the queued ones, so a slow page never paints over the next.
let routing = Promise.resolve();
let routeSeq = 0;
function route() {
  const seq = ++routeSeq;
  const run = routing.then(() => (seq === routeSeq ? routeNow() : undefined));
  routing = run.catch(() => {});          // one address that fails must not stop the next ones
  return run;
}

async function routeNow() {
  const raw = location.hash.slice(1);
  let h = raw;
  try { h = decodeURIComponent(raw); } catch { /* a bare % in a file name: route the address as it is */ }
  const [, view = '', rest = ''] = h.match(/^\/([\w-]*)\/?(.*)$/) || [];
  if ($('#palette').open) $('#palette').close();
  if (['pipeline', 'ask', 'kpis', 'ci', 'libs', 'data', 'interview', 'sync', 'kanban'].includes(view) && !STATIC && window.CamaronNative
      || RUNS && TALLER.includes(view) && window.CamaronNative) {
    CURRENT = '';
    drawChrome(view, { nativeView: true });
    drawToc(null);
    return window.CamaronNative.show(view, rest);
  }
  window.CamaronNative?.hide();
  try {
    if (view === 'boards') return location.replace('#/arch');   // boards were removed in 4.49
    if (view === 'docs' || view === 'doc') {
      if (!rest) return await showDocsHome();
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
    if (view === 'code') return await showCodeTab(rest);
    if (view === 'review' || view === 'status') return await showReview();
    if (view === 'search') return await showSearch(rest);
    if (view === 'new' && !STATIC) return newPage();
    if (['arch', 'plan', 'quality', 'taller'].includes(view)) return showZone(view);
    return await showStart();                 // #/, an unknown address, or a live-only view in the static export
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
// The zones come with the React bundle (a module script, run after these scripts): routing waits for both, or for
// the page's load event if the bundle failed (the docs still show, without breadcrumbs).
const zonesReady = () => (window.CamaronZones ? Promise.resolve() : new Promise((ok) => {
  addEventListener('camaron:native-ready', ok, { once: true });
  addEventListener('load', ok, { once: true });
}));
// In the app, whether this kit is a checkout with its tests (the Taller's Kit dev view).
const appInfo = () => (RUNS ? api('app/info').then((i) => { T.kitdev = i.kitdev; }, () => {}) : Promise.resolve());
Promise.all([loadTree(), zonesReady()]).then(appInfo).then(() => {
  if (!store.get('cam-lang')) {           // first visit: the browser's language when the docs are translated to it
    const nav = (navigator.language || 'en').slice(0, 2);
    if (T.langs.includes(nav)) lang = nav;
  }
  return route();
}).catch((e) => { drawChrome('docs'); $('#main').innerHTML = `<div class="page"><h1>${esc(t('unreachable'))}</h1><p>${esc(e.message)}</p></div>`; });
