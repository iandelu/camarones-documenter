'use strict';
const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const STATIC = $('meta[name="cam-mode"]').content === 'static';
const TRUST = { confirmed: '✅', draft: '🤖', 'needs-reconfirm': '⚠️' };
const LANG_NAMES = { en: 'English', es: 'Español', fr: 'Français', de: 'Deutsch', pt: 'Português', it: 'Italiano' };

const I18N = {
  en: {
    docs: 'Docs', c4: 'Architecture (C4)', code: 'Code graph', wikis: 'Wikis', review: 'Review',
    search: 'Search the docs… (Enter: full text)', newPage: '+ New page', general: 'General', wide: 'Toggle full width',
    edit: 'Edit', editForge: 'Edit in the repository', confirm: '✅ Confirm as correct', requestChange: '✏️ Request a change',
    'banner.draft': 'AI-generated draft — not yet confirmed by a human. Verify it against the code before relying on it.',
    'banner.needs-reconfirm': 'Changed after a human confirmed it — pending re-confirmation.',
    confirmedBy: 'confirmed by', humanOwned: '✍️ human-owned page', noTranslation: 'No {lang} translation yet — showing English.',
    outdatedTranslation: 'This translation is older than the English page.',
    pendingComments: 'Pending review comments', sources: 'Sources', emptyPage: '_Nothing here yet — use Edit to write it._',
    confirmTitle: 'Confirm this page', confirmHelp: 'You checked it against how the system really works. Agents will treat it as the source of truth.',
    yourName: 'Your name', cancel: 'Cancel', send: 'Send', save: 'Save', create: 'Create',
    fbHelp: 'Describe what is wrong or missing. The next AI session applies it (unit review-fixes).',
    editing: 'Editing', confirmedWarn: 'This page is confirmed: saving a change makes it “needs re-confirmation”.',
    commitMsg: 'What changed? (commit message)', commitBox: 'commit to cam-docs', saved: 'Saved', savedCommitted: 'Saved and committed',
    nothingToCommit: 'Saved (nothing to commit)', confirmedToast: 'Confirmed', commentSaved: 'Comment saved',
    translation: 'translation', newTitle: 'Title', newPath: 'section/page.md (e.g. guides/onboarding.md)',
    noDocs: 'No documentation yet', noDocsHelp: 'Run the next unit from the Camarones wizard, or create a page.',
    noMatch: 'No pages match.', results: 'Results for', noResults: 'No page mentions it.',
    reviewTitle: 'Review & status', planUnits: 'Plan {done}/{total} units · {pages} pages',
    waiting: 'Waiting for a human', allConfirmed: 'Nothing — all confirmed.', changeRequests: 'Change requests not applied yet',
    none: 'None.', codeChanged: 'Code changed since the docs were updated', allDocumented: 'All repos documented at their current commit.',
    askAgent: 'Ask an agent: “update the docs for the latest changes” (skill cam-docs-update).', checks: 'Checks', allPass: 'All checks pass.',
    files: 'files', rebuild: '↻ Rebuild', build: 'Build', builtAt: 'built {when}', stale: 'out of date — the source changed since',
    notBuilt: 'Not built yet.', noC4: 'There is no C4 model yet — the arch-system unit writes docs/architecture/*.c4.',
    noGraph: 'No code graph yet.', allRepos: 'All repos (merged)', openTab: 'Open in a new tab',
    wikisHelp: 'OpenWiki writes one wiki per repo (cam-docs/wikis/<repo>/). Its pages also appear under Docs → repos/<repo>.',
    noWiki: 'no wiki yet', pages: '{n} pages', updated: 'updated {when}', unit: 'plan unit', read: 'Read', graph: 'Graph',
    generate: 'Generate wiki', update: 'Update wiki', via: 'via', notCloned: 'not cloned',
    notChosen: 'no wiki for this repo (choose repos in the wizard → Wikis)', needBrief: 'first run its repo-brief unit (it writes INSTRUCTIONS.md)',
    noEngine: 'OpenWiki cannot run from here yet: save a provider key once with `openwiki auth configure openai` (or anthropic, gemini, openrouter) in a terminal, or install Claude Code / Codex so an agent writes it.',
    running: 'running…', done: 'done', failed: 'failed', jobStarted: 'Started: {label}',
    readOnly: 'Read-only portal (export). To edit, confirm or generate wikis locally run <code>camarones up</code>.',
    unreachable: 'Cannot reach the docs server', error: 'Error', justNow: 'just now',
  },
  es: {
    docs: 'Docs', c4: 'Arquitectura (C4)', code: 'Grafo de código', wikis: 'Wikis', review: 'Revisión',
    search: 'Buscar en la doc… (Enter: texto completo)', newPage: '+ Nueva página', general: 'General', wide: 'Ancho completo',
    edit: 'Editar', editForge: 'Editar en el repositorio', confirm: '✅ Confirmar como correcta', requestChange: '✏️ Pedir un cambio',
    'banner.draft': 'Borrador generado por IA — aún no confirmado por un humano. Verifícalo contra el código antes de fiarte.',
    'banner.needs-reconfirm': 'Modificado tras la confirmación humana — pendiente de reconfirmar.',
    confirmedBy: 'confirmada por', humanOwned: '✍️ página de un humano', noTranslation: 'Aún no hay traducción {lang} — se muestra en inglés.',
    outdatedTranslation: 'Esta traducción es anterior a la página en inglés.',
    pendingComments: 'Comentarios de revisión pendientes', sources: 'Fuentes', emptyPage: '_Aún no hay nada — usa Editar para escribirla._',
    confirmTitle: 'Confirmar esta página', confirmHelp: 'La has comprobado contra cómo funciona de verdad el sistema. Los agentes la tratarán como fuente de verdad.',
    yourName: 'Tu nombre', cancel: 'Cancelar', send: 'Enviar', save: 'Guardar', create: 'Crear',
    fbHelp: 'Describe qué está mal o falta. La próxima sesión de IA lo aplica (unidad review-fixes).',
    editing: 'Editando', confirmedWarn: 'Esta página está confirmada: al guardar un cambio pasa a “pendiente de reconfirmar”.',
    commitMsg: '¿Qué cambió? (mensaje del commit)', commitBox: 'commit en cam-docs', saved: 'Guardado', savedCommitted: 'Guardado y commit hecho',
    nothingToCommit: 'Guardado (nada que commitear)', confirmedToast: 'Confirmada', commentSaved: 'Comentario guardado',
    translation: 'traducción', newTitle: 'Título', newPath: 'seccion/pagina.md (p. ej. guides/onboarding.md)',
    noDocs: 'Aún no hay documentación', noDocsHelp: 'Lanza la siguiente unidad desde el asistente de Camarones, o crea una página.',
    noMatch: 'Ninguna página coincide.', results: 'Resultados de', noResults: 'Ninguna página lo menciona.',
    reviewTitle: 'Revisión y estado', planUnits: 'Plan {done}/{total} unidades · {pages} páginas',
    waiting: 'Esperando a un humano', allConfirmed: 'Nada — todo confirmado.', changeRequests: 'Peticiones de cambio sin aplicar',
    none: 'Ninguna.', codeChanged: 'Código cambiado desde la última actualización de la doc', allDocumented: 'Todos los repos documentados en su commit actual.',
    askAgent: 'Pide a un agente: “actualiza la doc con los últimos cambios” (skill cam-docs-update).', checks: 'Comprobaciones', allPass: 'Todo correcto.',
    files: 'ficheros', rebuild: '↻ Regenerar', build: 'Generar', builtAt: 'generado {when}', stale: 'desactualizado — la fuente cambió desde entonces',
    notBuilt: 'Aún no generado.', noC4: 'Aún no hay modelo C4 — la unidad arch-system escribe docs/architecture/*.c4.',
    noGraph: 'Aún no hay grafo de código.', allRepos: 'Todos los repos (fusionado)', openTab: 'Abrir en otra pestaña',
    wikisHelp: 'OpenWiki escribe una wiki por repo (cam-docs/wikis/<repo>/). Sus páginas también salen en Docs → repos/<repo>.',
    noWiki: 'sin wiki', pages: '{n} páginas', updated: 'actualizada {when}', unit: 'unidad del plan', read: 'Leer', graph: 'Grafo',
    generate: 'Generar wiki', update: 'Actualizar wiki', via: 'con', notCloned: 'sin clonar',
    notChosen: 'sin wiki para este repo (elige repos en el asistente → Wikis)', needBrief: 'antes ejecuta su unidad repo-brief (escribe INSTRUCTIONS.md)',
    noEngine: 'OpenWiki aún no puede lanzarse desde aquí: guarda una clave de proveedor una vez con `openwiki auth configure openai` (o anthropic, gemini, openrouter) en una terminal, o instala Claude Code / Codex para que la escriba un agente.',
    running: 'en curso…', done: 'hecho', failed: 'falló', jobStarted: 'Lanzado: {label}',
    readOnly: 'Portal de solo lectura (exportado). Para editar, confirmar o generar wikis en local ejecuta <code>camarones up</code>.',
    unreachable: 'No se puede conectar con el servidor de la doc', error: 'Error', justNow: 'ahora mismo',
  },
};

let T = { docs: [], langs: [], codeGraphs: [], engines: [], repos: [] };
let SEARCH_INDEX = null;
const store = { get: (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };
let lang = store.get('cam-lang');           // '' = English (canonical docs); otherwise a translation code
const ui = () => I18N[lang] || I18N.en;
const t = (k, vars = {}) => (ui()[k] ?? I18N.en[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '');
const ago = (sec) => {
  if (!sec) return '';
  const d = new Date(sec * 1000);
  return (Date.now() - d) < 60000 ? t('justNow') : d.toLocaleString(lang || 'en', { dateStyle: 'medium', timeStyle: 'short' });
};

async function api(name, params = {}, body) {
  if (STATIC) {
    if (body !== undefined) throw new Error('read-only');
    if (name === 'doc') {
      const tryGet = async (l) => { const r = await fetch(`api/doc/${l || '_'}/${params.path}.json`); return r.ok ? r.json() : null; };
      const d = params.lang && await tryGet(params.lang);
      if (d) return d;
      const en = await tryGet('');
      if (!en) throw new Error(`unknown page ${params.path}`);
      return params.lang ? { ...en, lang: params.lang, exists: false, raw: '' } : en;
    }
    if (name === 'search') return staticSearch(params.q);
    const r = await fetch(`api/${name}.json`);
    if (!r.ok) throw new Error(r.statusText);
    return r.json();
  }
  const qs = new URLSearchParams(params).toString();
  const r = await fetch(`api/${name}${qs ? '?' + qs : ''}`, body === undefined ? {} : {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Camarones': '1' }, body: JSON.stringify(body),
  });
  const data = await r.json();
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

async function staticSearch(q) {
  SEARCH_INDEX ||= await (await fetch('api/search.json')).json();
  const terms = (q.toLowerCase().match(/\w+/g) || []).filter((w) => w.length > 1);
  if (!terms.length) return [];
  const want = SEARCH_INDEX.some((e) => e.lang === lang) ? lang : '';
  return SEARCH_INDEX.filter((e) => e.lang === want).map((e) => {
    const low = e.text.toLowerCase();
    const score = terms.reduce((s, w) => s + low.split(w).length - 1 + (e.path.toLowerCase().includes(w) ? 5 : 0), 0);
    const lines = e.text.split('\n').filter((l) => terms.some((w) => l.toLowerCase().includes(w))).slice(0, 3).map((l) => l.trim().slice(0, 240));
    return { ...e, score, lines };
  }).filter((e) => e.score).sort((a, b) => b.score - a.score).slice(0, 20);
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => { el.hidden = true; }, 3500);
}

const dark = matchMedia('(prefers-color-scheme: dark)').matches;
if (window.mermaid) mermaid.initialize({ startOnLoad: false, theme: dark ? 'dark' : 'default' });

function render(md, docPath) {
  const body = md.replace(/^---\n[\s\S]*?\n---\n?/, '').replace(/^\s*#\s+.+\n/, '');   // the page header shows the title
  const el = document.createElement('div');
  el.className = 'doc';
  el.innerHTML = DOMPurify.sanitize(marked.parse(body, { gfm: true }));
  const base = docPath.split('/').slice(0, -1);
  const resolve = (href) => {
    const parts = [...base];
    for (const p of href.split('/')) { if (p === '..') parts.pop(); else if (p && p !== '.') parts.push(p); }
    return parts.join('/');
  };
  el.querySelectorAll('a[href]').forEach((a) => {
    const href = a.getAttribute('href');
    if (/^[a-z]+:|^#|^\//i.test(href)) return;
    const [file, anchor] = href.split('#');
    if (file.endsWith('.md')) a.setAttribute('href', `#/docs/${resolve(file)}${anchor ? '::' + anchor : ''}`);
  });
  el.querySelectorAll('img[src]').forEach((img) => {
    const src = img.getAttribute('src');
    if (!/^[a-z]+:|^\//i.test(src)) img.src = 'raw/' + resolve(src);
  });
  el.querySelectorAll('pre code.language-mermaid').forEach((c) => {
    const d = document.createElement('div');
    d.className = 'mermaid';
    d.textContent = c.textContent;
    c.parentElement.replaceWith(d);
  });
  return el;
}

async function drawMermaid(root) {
  const nodes = root.querySelectorAll('.mermaid');
  if (nodes.length && window.mermaid) { try { await mermaid.run({ nodes }); } catch (e) { console.warn(e); } }
}

// ---------- chrome ----------
const TABS = [['docs', '#/docs'], ['c4', '#/c4'], ['code', '#/code'], ['wikis', '#/wikis'], ['review', '#/review']];

function drawChrome(active) {
  document.documentElement.lang = lang || 'en';
  $('#tabs').innerHTML = TABS.map(([k, href]) => `<a href="${href}" class="${k === active ? 'on' : ''}">${esc(t(k))}</a>`).join('');
  $('#search').placeholder = t('search');
  $('#wide').title = t('wide');
  $('#new').textContent = t('newPage');
  $('#new').hidden = STATIC;
  $('#ro').hidden = !STATIC;
  $('#ro').innerHTML = t('readOnly');
  const langs = ['', ...T.langs];
  $('#lang').innerHTML = langs.map((l) => `<option value="${l}">${esc(LANG_NAMES[l || 'en'] || l)}</option>`).join('');
  $('#lang').value = langs.includes(lang) ? lang : '';
  const full = active !== 'docs' && active !== 'review' && active !== 'search';
  document.body.classList.toggle('viewer-mode', full);
  $('#side').hidden = full;
}

function drawTree(active) {
  const q = $('#search').value.trim().toLowerCase();
  const groups = {};
  for (const d of T.docs) {
    if (q && !(d.title + ' ' + d.path).toLowerCase().includes(q)) continue;
    const g = d.path.includes('/') ? d.path.split('/').slice(0, d.path.startsWith('repos/') ? 2 : 1).join('/') : '';
    (groups[g] ||= []).push(d);
  }
  const order = Object.entries(groups).sort(([a], [b]) => (b === '') - (a === '')).map(([g, items]) => [g || t('general'), items]);
  $('#tree').innerHTML = order.map(([g, items]) => `<h4>${esc(g)}</h4>` + items.map((d) =>
    `<a href="#/docs/${esc(d.path)}" class="${d.path === active ? 'on' : ''}" title="${esc(d.path)}">${TRUST[d.trust] || ''} ${esc(d.title)}</a>`
  ).join('')).join('') || `<p class="muted">${esc(t('noMatch'))}</p>`;
  $('#tree .on')?.scrollIntoView({ block: 'nearest' });
}

async function loadTree() {
  T = await api('tree');
  if (!T.langs.includes(lang)) lang = '';
  document.title = `🦐 ${T.project} — Camarones`;
  $('#project').textContent = T.project;
  const s = T.summary;
  $('#summary').textContent = `✅ ${s.confirmed} · 🤖 ${s.draft} · ⚠️ ${s['needs-reconfirm']}` + (T.feedback ? ` · ✏️ ${T.feedback}` : '');
}

// ---------- docs ----------
async function showDoc(path, anchor) {
  drawChrome('docs');
  drawTree(path);
  const d = await api('doc', { path, lang });
  const english = lang && !d.exists ? await api('doc', { path }) : null;
  const row = T.docs.find((r) => r.path === path) || {};
  const i18n = lang ? (row.i18n || {})[lang] : '';
  const edit = STATIC
    ? (T.editBase ? `<a class="button" href="${esc(T.editBase + d.file)}" target="_blank" rel="noopener">${esc(t('editForge'))} ↗</a>` : '')
    : `<button id="a-edit">${esc(t('edit'))}</button>
       ${d.trust !== 'confirmed' ? `<button id="a-confirm" class="ghost">${esc(t('confirm'))}</button>` : ''}
       <button id="a-fb" class="ghost">${esc(t('requestChange'))}</button>`;
  $('#main').innerHTML = `
    <h1>${esc(d.title)}</h1>
    <div class="meta">
      <span class="badge ${esc(d.trust)}">${TRUST[d.trust] || ''} ${esc(d.trust)}</span>
      <code>${esc(d.file)}</code>
      ${d.confirmed && d.confirmed.by ? `<span>${esc(t('confirmedBy'))} ${esc(d.confirmed.by)} · ${esc(String(d.confirmed.at).slice(0, 10))}</span>` : ''}
      ${d.owner === 'human' ? `<span>${esc(t('humanOwned'))}</span>` : ''}
    </div>
    ${lang && !d.exists ? `<div class="banner info">${esc(t('noTranslation', { lang: LANG_NAMES[lang] || lang }))}</div>` : ''}
    ${lang && d.exists && i18n === 'outdated' ? `<div class="banner">${esc(t('outdatedTranslation'))}</div>` : ''}
    ${t('banner.' + d.trust) !== 'banner.' + d.trust ? `<div class="banner ${esc(d.trust)}">${esc(t('banner.' + d.trust))}</div>` : ''}
    <div class="actions">${edit}</div>
    <div id="panel"></div>
    ${d.feedback.length ? `<div class="box"><b>${esc(t('pendingComments'))}</b><ul class="list">${d.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('')}</ul></div>` : ''}
    <div id="body"></div>
    ${d.sources.length ? `<div class="box"><b>${esc(t('sources'))}</b><ul class="list">${d.sources.map((s) => `<li><code>${esc(s)}</code></li>`).join('')}</ul></div>` : ''}`;
  const body = render(d.exists ? d.raw : english?.exists ? english.raw : t('emptyPage'), path);
  $('#body').append(body);
  await drawMermaid(body);
  if (anchor) document.getElementById(anchor)?.scrollIntoView();
  else window.scrollTo(0, 0);
  if (STATIC) return;
  $('#a-edit').onclick = () => editDoc(d);
  $('#a-confirm')?.addEventListener('click', () => confirmPanel(d));
  $('#a-fb').onclick = () => feedbackPanel(d);
}

function confirmPanel(d) {
  $('#panel').innerHTML = `<div class="box"><b>${esc(t('confirmTitle'))}</b>
    <p class="muted">${esc(t('confirmHelp'))}</p>
    <div class="row"><input id="c-by" value="${esc(T.reviewer)}" placeholder="${esc(t('yourName'))}" style="max-width:16rem">
    <button id="c-go">${esc(t('confirm'))}</button><button id="c-x" class="ghost">${esc(t('cancel'))}</button></div></div>`;
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
    <button id="f-go">${esc(t('send'))}</button><button id="f-x" class="ghost">${esc(t('cancel'))}</button></div></div>`;
  $('#f-x').onclick = () => { $('#panel').innerHTML = ''; };
  $('#f-go').onclick = async () => {
    if (!$('#f-text').value.trim()) return;
    await api('feedback', {}, { path: d.path, text: $('#f-text').value, by: $('#f-by').value });
    await afterChange(d.path, t('commentSaved'));
  };
}

function editDoc(d) {
  $('#main').innerHTML = `<h1>${esc(t('editing'))}: ${esc(d.title)}</h1>
    <div class="meta"><code>${esc(d.file)}</code>${lang ? ` · ${esc(t('translation'))} ${esc(lang)}` : ''}</div>
    ${d.trust === 'confirmed' ? `<div class="banner">${esc(t('confirmedWarn'))}</div>` : ''}
    <div class="editor"><textarea id="e-src" spellcheck="true"></textarea><div class="preview" id="e-prev"></div></div>
    <div class="row">
      <input id="e-msg" placeholder="${esc(t('commitMsg'))}" style="flex:1;min-width:14rem">
      <label><input type="checkbox" id="e-commit" checked> ${esc(t('commitBox'))}</label>
      <button id="e-save">${esc(t('save'))}</button><button id="e-x" class="ghost">${esc(t('cancel'))}</button>
    </div>`;
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
      location.hash = `#/docs/${d.path}`;
      route();
    } catch (e) { toast(e.message); $('#e-save').disabled = false; }
  };
}

async function afterChange(path, msg) {
  toast(msg);
  await loadTree();
  await showDoc(path);
}

function newPage() {
  drawChrome('docs');
  $('#main').innerHTML = `<h1>${esc(t('newPage').replace('+ ', ''))}</h1><div class="box">
    <input id="n-title" placeholder="${esc(t('newTitle'))}">
    <div class="row"><input id="n-path" placeholder="${esc(t('newPath'))}"></div>
    <div class="row"><button id="n-go">${esc(t('create'))}</button></div></div>`;
  $('#n-title').oninput = () => { $('#n-path').value = 'guides/' + $('#n-title').value.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') + '.md'; };
  $('#n-go').onclick = async () => {
    try {
      const d = await api('new', {}, { path: $('#n-path').value, title: $('#n-title').value });
      await loadTree();
      location.hash = `#/docs/${d.path}`;
      editDoc(d);
    } catch (e) { toast(e.message); }
  };
}

async function showSearch(q) {
  drawChrome('search');
  drawTree('');
  $('#search').value = q;
  const hits = await api('search', { q });
  const mark = (s) => { let h = esc(s); for (const w of q.match(/\w{2,}/g) || []) h = h.replace(new RegExp(`(${w})`, 'gi'), '<mark>$1</mark>'); return h; };
  $('#main').innerHTML = `<h1>${esc(t('results'))} “${esc(q)}”</h1>` + (hits.map((h) =>
    `<div class="hit"><a href="#/docs/${esc(h.path)}">${TRUST[h.trust] || ''} ${esc(h.title)}</a> <span class="muted">${esc(h.path)}</span>
     ${h.lines.map((l) => `<div class="snip">${mark(l)}</div>`).join('')}</div>`).join('') || `<p class="muted">${esc(t('noResults'))}</p>`);
}

// ---------- review ----------
async function showReview() {
  drawChrome('review');
  drawTree('');
  const s = await api('status');
  const changed = Object.entries(s.changes).filter(([, c]) => c.status !== 'up-to-date');
  $('#main').innerHTML = `<h1>${esc(t('reviewTitle'))}</h1>
    <p class="muted">${esc(t('planUnits', { done: s.plan.done, total: s.plan.total, pages: T.summary.total }))}</p>
    <div class="box"><b>${esc(t('waiting'))} (${s.queue.length})</b><ul class="list">${s.queue.map((r) =>
      `<li>${TRUST[r.trust]} <a href="#/docs/${esc(r.path)}">${esc(r.title)}</a> <span class="muted">${esc(r.path)}</span></li>`).join('') || `<li class="muted">${esc(t('allConfirmed'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('changeRequests'))} (${s.feedback.length})</b><ul class="list">${s.feedback.map((f) => `<li>${esc(f.slice(6))}</li>`).join('') || `<li class="muted">${esc(t('none'))}</li>`}</ul></div>
    <div class="box"><b>${esc(t('codeChanged'))} (${changed.length})</b><ul class="list">${changed.map(([n, c]) =>
      `<li><b>${esc(n)}</b> — ${esc(c.status)}${c.files ? ` (${c.files.length} ${esc(t('files'))})` : ''}</li>`).join('') || `<li class="muted">${esc(t('allDocumented'))}</li>`}</ul>
      <p class="muted">${esc(t('askAgent'))}</p></div>
    <div class="box"><b>${esc(t('checks'))}</b><ul class="list">${[...s.check.errors.map((e) => `<li>❌ ${esc(e)}</li>`), ...s.check.warnings.map((w) => `<li>⚠️ ${esc(w)}</li>`)].join('') || `<li class="muted">${esc(t('allPass'))}</li>`}</ul></div>`;
}

// ---------- jobs (live mode: builds and wiki runs) ----------
function watchJob(job, logEl, onEnd) {
  let since = 0;
  toast(t('jobStarted', { label: job.label }));
  const tick = async () => {
    try {
      const j = await api(`jobs/${job.id}`, { since });
      since = j.lines;
      if (logEl && j.log.length) { logEl.hidden = false; logEl.textContent += j.log.join('\n') + '\n'; logEl.scrollTop = logEl.scrollHeight; }
      if (j.status === 'running') return setTimeout(tick, 1000);
      toast(`${j.label}: ${t(j.status)}`);
      onEnd?.(j);
    } catch (e) { toast(e.message); }
  };
  tick();
}

function viewerBar(parts, rebuild) {
  return `<div class="vbar">${parts.filter(Boolean).join('')}
    ${!STATIC && rebuild ? `<button id="v-build" class="small">${esc(rebuild)}</button>` : ''}
    <pre id="v-log" class="joblog inline" hidden></pre></div>`;
}

function bindBuild(what, repo) {
  $('#v-build')?.addEventListener('click', async () => {
    $('#v-build').disabled = true;
    try { watchJob(await api('build', {}, { what, repo }), $('#v-log'), async () => { await loadTree(); route(); }); }
    catch (e) { toast(e.message); $('#v-build').disabled = false; }
  });
}

async function showC4() {
  drawChrome('c4');
  const v = (await api('viewers')).c4;
  const state = v.exists ? `<span class="muted">${esc(t('builtAt', { when: ago(v.at) }))}</span>${v.stale ? ` <span class="warn">⚠️ ${esc(t('stale'))}</span>` : ''}`
    : `<span class="muted">${esc(v.model ? t('notBuilt') : t('noC4'))}</span>`;
  $('#main').innerHTML = viewerBar([`<b>${esc(t('c4'))}</b>`, state,
    v.exists ? `<a href="architecture/" target="_blank">${esc(t('openTab'))} ↗</a>` : ''], v.model ? (v.exists ? t('rebuild') : t('build')) : '')
    + (v.exists ? '<iframe class="viewer" src="architecture/" title="C4"></iframe>' : '');
  bindBuild('c4');
}

async function showCode(repo) {
  drawChrome('code');
  const v = await api('viewers');
  const names = Object.keys(v.graphs);
  repo = names.includes(repo) ? repo : (names[0] || '');
  const g = v.graphs[repo];
  const src = repo === 'all' ? 'code-graph/' : `code-graph/${encodeURIComponent(repo)}/`;
  const sel = names.length ? `<select id="v-repo">${names.map((n) => `<option value="${esc(n)}" ${n === repo ? 'selected' : ''}>${esc(n === 'all' ? t('allRepos') : n)}</option>`).join('')}</select>` : '';
  const state = g ? `<span class="muted">${esc(t('builtAt', { when: ago(g.at) }))}</span>${g.stale ? ` <span class="warn">⚠️ ${esc(t('stale'))}</span>` : ''}`
    : `<span class="muted">${esc(t('noGraph'))}</span>`;
  $('#main').innerHTML = viewerBar([`<b>${esc(t('code'))}</b>`, sel, state, g ? `<a href="${src}" target="_blank">${esc(t('openTab'))} ↗</a>` : ''],
    v.graphify ? (names.length ? t('rebuild') : t('build')) : '') + (g ? `<iframe class="viewer" src="${src}" title="code graph"></iframe>` : '');
  $('#v-repo')?.addEventListener('change', (e) => { location.hash = `#/code/${e.target.value}`; });
  bindBuild('graph');
}

async function showWikis(open) {
  drawChrome('wikis');
  const rows = await api('wikis');
  const engines = T.engines || [];
  const engSel = engines.length > 1 ? `<select class="w-eng">${engines.map((e) => `<option>${esc(e)}</option>`).join('')}</select>` : '';
  $('#main').innerHTML = `<div class="page"><h1>📚 ${esc(t('wikis'))} <span class="muted small">OpenWiki</span></h1>
    <p class="muted">${esc(t('wikisHelp'))}</p>
    ${!STATIC && !engines.length ? `<div class="banner">${esc(t('noEngine'))}</div>` : ''}
    <div class="cards">${rows.map((w) => `<div class="card ${w.repo === open ? 'open' : ''}" data-repo="${esc(w.repo)}">
      <div class="card-h"><b>${esc(w.repo)}</b>
        <span class="muted">${w.pages ? esc(t('pages', { n: w.pages })) + ' · ' + esc(t('updated', { when: ago(w.at) })) : esc(w.cloned ? t('noWiki') : t('notCloned'))}</span>
        ${w.stale ? `<span class="warn">⚠️ ${esc(t('stale'))}</span>` : ''}
        ${w.unit ? `<span class="chip">${esc(t('unit'))}: ${esc(w.unit)}</span>` : ''}</div>
      <div class="row">
        ${w.index ? `<a class="button ghost small" href="#/docs/${esc(w.index)}">${esc(t('read'))}</a>` : ''}
        ${w.graph ? `<button class="ghost small w-graph">${esc(t('graph'))}</button>` : ''}
        ${!STATIC && !w.chosen && !w.pages ? `<span class="muted small">${esc(t('notChosen'))}</span>` : ''}
        ${!STATIC && w.chosen && !w.ready ? `<span class="muted small">${esc(t('needBrief'))}</span>` : ''}
        ${!STATIC && engines.length && w.cloned && (w.chosen || w.pages) && w.ready ? `<button class="small w-gen">${esc(w.pages ? t('update') : t('generate'))}</button>${engSel ? ` ${esc(t('via'))} ${engSel}` : ` <span class="muted small">${esc(t('via'))} ${esc(engines[0])}</span>`}` : ''}
      </div>
      <pre class="joblog" hidden></pre>
      <div class="wgraph"></div></div>`).join('')}</div></div>`;
  $('#main').querySelectorAll('.card').forEach((card) => {
    const repo = card.dataset.repo;
    card.querySelector('.w-graph')?.addEventListener('click', () => {
      const box = card.querySelector('.wgraph');
      box.innerHTML = box.innerHTML ? '' : `<iframe class="viewer small" src="wiki-graph/${encodeURIComponent(repo)}/" title="wiki graph"></iframe>`;
    });
    card.querySelector('.w-gen')?.addEventListener('click', async (e) => {
      e.target.disabled = true;
      const engine = card.querySelector('.w-eng')?.value || '';
      try { watchJob(await api('wiki', {}, { repo, engine }), card.querySelector('.joblog'), async (j) => { await loadTree(); if (j.status === 'done' && location.hash.startsWith('#/wikis')) showWikis(repo); else e.target.disabled = false; }); }
      catch (err) { toast(err.message); e.target.disabled = false; }
    });
  });
  if (!STATIC) {       // reattach to a wiki run started earlier (from this page or another tab)
    const jobs = await api('jobs');
    for (const j of jobs.filter((x) => x.kind === 'wiki' && x.status === 'running')) {
      const card = [...$('#main').querySelectorAll('.card')].find((c) => j.label.endsWith(' ' + c.dataset.repo));
      if (card) { card.querySelector('.w-gen')?.setAttribute('disabled', ''); watchJob(j, card.querySelector('.joblog'), (r) => { if (r.status === 'done') showWikis(card.dataset.repo); }); }
    }
  }
}

// ---------- routing ----------
async function route() {
  const h = decodeURIComponent(location.hash.slice(1));
  const [, view = '', rest = ''] = h.match(/^\/([\w-]*)\/?(.*)$/) || [];
  try {
    if (view === 'docs' || view === 'doc') {
      if (rest) { const [path, anchor] = rest.split('::'); return await showDoc(path, anchor); }
    } else if (view === 'c4') return await showC4();
    else if (view === 'code') return await showCode(rest);
    else if (view === 'wikis') return await showWikis(rest);
    else if (view === 'review' || view === 'status') return await showReview();
    else if (view === 'search') return await showSearch(rest);
    else if (view === 'new' && !STATIC) return newPage();
    const first = T.docs.find((d) => d.path === 'index.md') || T.docs.find((d) => d.path.startsWith('overview')) || T.docs[0];
    if (first) return await showDoc(first.path);
    drawChrome('docs');
    drawTree('');
    $('#main').innerHTML = `<h1>${esc(t('noDocs'))}</h1><p>${esc(t('noDocsHelp'))}</p>`;
  } catch (e) {
    $('#main').innerHTML = `<h1>${esc(t('error'))}</h1><p>${esc(e.message)}</p>`;
  }
}

$('#search').oninput = () => { if (!$('#side').hidden) drawTree((decodeURIComponent(location.hash).match(/#\/docs?\/([^:]+)/) || [])[1]); };
$('#search').onkeydown = (e) => { if (e.key === 'Enter' && e.target.value.trim()) location.hash = `#/search/${encodeURIComponent(e.target.value.trim())}`; };
$('#lang').onchange = (e) => { lang = e.target.value; store.set('cam-lang', lang); route(); };
$('#wide').onclick = () => { document.body.classList.toggle('wide'); store.set('cam-wide', document.body.classList.contains('wide') ? '1' : ''); };
$('#new').onclick = () => { location.hash = '#/new'; };
if (store.get('cam-wide')) document.body.classList.add('wide');
addEventListener('hashchange', route);
loadTree().then(() => {
  if (!store.get('cam-lang')) {           // first visit: the browser's language when the docs are translated to it
    const nav = (navigator.language || 'en').slice(0, 2);
    if (T.langs.includes(nav)) lang = nav;
  }
  return route();
}).catch((e) => { drawChrome('docs'); $('#main').innerHTML = `<h1>${esc(t('unreachable'))}</h1><p>${esc(e.message)}</p>`; });
