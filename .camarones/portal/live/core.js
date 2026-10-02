'use strict';
// Shared state and helpers. Plain scripts (no modules, no build): core → doc → c4 → wiki → app share one global scope.
const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const STATIC = $('meta[name="cam-mode"]').content === 'static';
const TRUST = { confirmed: '✅', draft: '✨', 'needs-reconfirm': '⚠️' };
const LANG_NAMES = { en: 'English', es: 'Español', fr: 'Français', de: 'Deutsch', pt: 'Português', it: 'Italiano' };
const SECTION_ICONS = { overview: '🧭', architecture: '🏗️', domain: '📖', flows: '🔀', data: '🗄️', deployment: '🚀',
  decisions: '⚖️', quality: '🧪', guides: '🧑‍🏫', repos: '📦', security: '🔒', interview: '🎙️' };

const I18N = {
  en: {
    docs: 'Docs', c4: 'Architecture', code: 'Code graph', wikis: 'Wikis', review: 'Review', home: 'Home',
    search: 'Search', searchPh: 'Search pages and content…', searchHint: '↑↓ to move · Enter to open · Esc to close',
    searchAll: 'All results for “{q}”', titles: 'Pages', content: 'Content', inNotes: 'working note',
    newPage: '+ New page', general: 'General', notes: 'Working notes',
    notesHelp: 'Discovery, interviews and questionnaires: what agents used to write the docs.',
    onThisPage: 'On this page', prev: 'Previous', next: 'Next', menu: 'Menu', theme: 'Switch light / dark',
    copy: 'Copy', copied: 'Copied', zoom: 'Full screen', close: 'Close',
    'callout.note': 'Note', 'callout.tip': 'Tip', 'callout.important': 'Important', 'callout.warning': 'Warning', 'callout.caution': 'Caution',
    'sec.overview': 'Overview', 'sec.architecture': 'Architecture', 'sec.domain': 'Domain', 'sec.flows': 'Flows',
    'sec.data': 'Data', 'sec.deployment': 'Deployment', 'sec.decisions': 'Decisions', 'sec.quality': 'Quality',
    'sec.guides': 'Guides', 'sec.repos': 'Services', 'sec.security': 'Security', 'sec.interview': 'Interviews',
    'secd.overview': 'What the system is and the tools around it', 'secd.architecture': 'C4 model, containers and decisions behind them',
    'secd.domain': 'Bounded contexts, language and rules', 'secd.flows': 'Business flows end to end, step by step',
    'secd.data': 'Data models, stores and ownership', 'secd.deployment': 'Environments and how it runs',
    'secd.decisions': 'Why things are the way they are', 'secd.quality': 'Tests, risks and known debt',
    'secd.guides': 'How-tos and onboarding', 'secd.repos': 'One page per service', 'secd.security': 'Threats and controls',
    'secd.wikis': 'Per-repo wikis, every claim anchored to code', 'secd.c4': 'Interactive C4 diagrams',
    homeLead: 'Architecture, domain, flows and decisions in one place — for people and agents.',
    homeEmpty: 'Nothing documented yet — your intern shrimp is still peeling the repos.',
    statPages: '{n} pages', statConfirmed: '{n}% confirmed', statFlows: '{n} flows', statViews: '{n} C4 views',
    systemContext: 'System context', explore: 'Explore',
    edit: 'Edit', editForge: 'Edit in the repository', confirm: '✅ Confirm as correct', requestChange: '✏️ Request a change',
    'banner.draft': 'AI-generated draft — not yet confirmed by a human. Verify it against the code before relying on it.',
    'banner.needs-reconfirm': 'Changed after a human confirmed it — pending re-confirmation.',
    'trust.confirmed': 'Confirmed', 'trust.draft': 'Draft', 'trust.needs-reconfirm': 'Needs re-confirmation',
    confirmedBy: 'confirmed by', humanOwned: '✍️ human-owned', noTranslation: 'No {lang} translation yet — showing English.',
    outdatedTranslation: 'This translation is older than the English page.',
    pendingComments: 'Pending review comments', sources: 'Sources', emptyPage: '_Nothing here yet — use Edit to write it._',
    confirmTitle: 'Confirm this page', confirmHelp: 'You checked it against how the system really works. Agents will treat it as the source of truth.',
    yourName: 'Your name', cancel: 'Cancel', send: 'Send', save: 'Save', create: 'Create',
    fbHelp: 'Describe what is wrong or missing. The next AI session applies it (unit review-fixes).',
    editing: 'Editing', confirmedWarn: 'This page is confirmed: saving a change makes it “needs re-confirmation”.',
    commitMsg: 'What changed? (commit message)', commitBox: 'commit to cam-docs', saved: 'Saved', savedCommitted: 'Saved and committed',
    nothingToCommit: 'Saved (nothing to commit)', confirmedToast: 'Confirmed', commentSaved: 'Comment saved',
    translation: 'translation', newTitle: 'Title', newPath: 'section/page.md (e.g. guides/onboarding.md)',
    noDocs: 'No documentation yet', noDocsHelp: 'Run the next unit from the Camarón wizard, or create a page.',
    noMatch: 'No pages match.', results: 'Results for', noResults: 'No page mentions it.',
    reviewTitle: 'Review & status', planUnits: 'Plan {done}/{total} units · {pages} pages',
    waiting: 'Waiting for a human', allConfirmed: 'Nothing — all confirmed.', changeRequests: 'Change requests not applied yet',
    none: 'None.', codeChanged: 'Code changed since the docs were updated', allDocumented: 'All repos documented at their current commit.',
    askAgent: 'Ask an agent: “update the docs for the latest changes” (skill cam-docs-update).', checks: 'Checks', allPass: 'All checks pass.',
    files: 'files', rebuild: '↻ Rebuild', build: 'Build', builtAt: 'built {when}', stale: 'out of date — the source changed since',
    notBuilt: 'Not built yet.', noC4: 'There is no C4 model yet — the arch-system unit writes docs/architecture/*.c4.',
    noGraph: 'No code graph yet.', allRepos: 'All repos (merged)', openTab: 'Open in a new tab',
    views: 'Views', 'kind.system': 'System', 'kind.element': 'Containers & components', 'kind.dynamic': 'Flows',
    'kind.deployment': 'Deployment', explorer: 'Full explorer', openExplorer: 'Open in the explorer', readFlow: 'Read the flow',
    viewIn: 'Open in Architecture', c4Missing: 'The interactive diagram is not built yet.', c4Unavailable: 'Interactive diagrams need a newer C4 build — rebuild it.',
    diagram: 'Interactive diagram — click an element to explore',
    wikisHelp: 'OpenWiki writes one wiki per repo (cam-docs/wikis/<repo>/), every claim anchored to a file and line of code.',
    noWiki: 'no wiki yet', pages: '{n} pages', updated: 'updated {when}', unit: 'plan unit', read: 'Read', graph: 'Graph',
    generate: 'Generate wiki', update: 'Update wiki', via: 'via', notCloned: 'not cloned', linkedFrom: 'Linked from',
    wikiPages: 'Pages', allWikis: 'All wikis', noWikiPages: 'This repo has no wiki pages yet.', readPages: 'Read the pages',
    wikiOld: 'Written with the old, thinner wiki scope. Update it to get a complete wiki (modules, APIs, configuration, operations…).',
    graphBuilding: 'Building the wiki graph…', graphFailed: 'The wiki graph could not be built — read the pages instead.',
    notChosen: 'no wiki for this repo (choose repos in the wizard → Wikis)', needBrief: 'first run its repo-brief unit (it writes INSTRUCTIONS.md)',
    noEngine: 'OpenWiki cannot run from here yet: save a provider key once with `openwiki auth configure openai` (or anthropic, gemini, openrouter) in a terminal, or install Claude Code / Codex so an agent writes it.',
    running: 'running…', done: 'done', failed: 'failed', jobStarted: 'Started: {label}',
    readOnly: 'Read-only portal (export). To edit, confirm or generate wikis locally run <code>camaron up</code>.',
    unreachable: 'Cannot reach the docs server', error: 'Error', justNow: 'just now', notFound: 'Page not found',
  },
  es: {
    docs: 'Docs', c4: 'Arquitectura', code: 'Grafo de código', wikis: 'Wikis', review: 'Revisión', home: 'Inicio',
    search: 'Buscar', searchPh: 'Busca páginas y contenido…', searchHint: '↑↓ para moverte · Enter para abrir · Esc para cerrar',
    searchAll: 'Todos los resultados de «{q}»', titles: 'Páginas', content: 'Contenido', inNotes: 'nota de trabajo',
    newPage: '+ Nueva página', general: 'General', notes: 'Notas de trabajo',
    notesHelp: 'Discovery, entrevistas y cuestionarios: lo que usaron los agentes para escribir la doc.',
    onThisPage: 'En esta página', prev: 'Anterior', next: 'Siguiente', menu: 'Menú', theme: 'Cambiar claro / oscuro',
    copy: 'Copiar', copied: 'Copiado', zoom: 'Pantalla completa', close: 'Cerrar',
    'callout.note': 'Nota', 'callout.tip': 'Consejo', 'callout.important': 'Importante', 'callout.warning': 'Aviso', 'callout.caution': 'Precaución',
    'sec.overview': 'Visión general', 'sec.architecture': 'Arquitectura', 'sec.domain': 'Dominio', 'sec.flows': 'Flujos',
    'sec.data': 'Datos', 'sec.deployment': 'Despliegue', 'sec.decisions': 'Decisiones', 'sec.quality': 'Calidad',
    'sec.guides': 'Guías', 'sec.repos': 'Servicios', 'sec.security': 'Seguridad', 'sec.interview': 'Entrevistas',
    'secd.overview': 'Qué es el sistema y las herramientas que lo rodean', 'secd.architecture': 'Modelo C4, contenedores y las decisiones detrás',
    'secd.domain': 'Contextos, lenguaje y reglas de negocio', 'secd.flows': 'Flujos de negocio de punta a punta, paso a paso',
    'secd.data': 'Modelos de datos, almacenes y quién es dueño', 'secd.deployment': 'Entornos y cómo se ejecuta',
    'secd.decisions': 'Por qué las cosas son como son', 'secd.quality': 'Tests, riesgos y deuda conocida',
    'secd.guides': 'Guías prácticas y onboarding', 'secd.repos': 'Una página por servicio', 'secd.security': 'Amenazas y controles',
    'secd.wikis': 'Wikis por repo, cada afirmación anclada al código', 'secd.c4': 'Diagramas C4 interactivos',
    homeLead: 'Arquitectura, dominio, flujos y decisiones en un solo sitio, para personas y agentes.',
    homeEmpty: 'Aún no hay nada documentado: tu camarón becario sigue pelando los repos.',
    statPages: '{n} páginas', statConfirmed: '{n} % confirmado', statFlows: '{n} flujos', statViews: '{n} vistas C4',
    systemContext: 'Contexto del sistema', explore: 'Explorar',
    edit: 'Editar', editForge: 'Editar en el repositorio', confirm: '✅ Confirmar como correcta', requestChange: '✏️ Pedir un cambio',
    'banner.draft': 'Borrador generado por IA — aún no confirmado por un humano. Verifícalo contra el código antes de fiarte.',
    'banner.needs-reconfirm': 'Modificado tras la confirmación humana — pendiente de reconfirmar.',
    'trust.confirmed': 'Confirmada', 'trust.draft': 'Borrador', 'trust.needs-reconfirm': 'Pendiente de reconfirmar',
    confirmedBy: 'confirmada por', humanOwned: '✍️ escrita por un humano', noTranslation: 'Aún no hay traducción {lang} — se muestra en inglés.',
    outdatedTranslation: 'Esta traducción es anterior a la página en inglés.',
    pendingComments: 'Comentarios de revisión pendientes', sources: 'Fuentes', emptyPage: '_Aún no hay nada — usa Editar para escribirla._',
    confirmTitle: 'Confirmar esta página', confirmHelp: 'La has comprobado contra cómo funciona de verdad el sistema. Los agentes la tratarán como fuente de verdad.',
    yourName: 'Tu nombre', cancel: 'Cancelar', send: 'Enviar', save: 'Guardar', create: 'Crear',
    fbHelp: 'Describe qué está mal o falta. La próxima sesión de IA lo aplica (unidad review-fixes).',
    editing: 'Editando', confirmedWarn: 'Esta página está confirmada: al guardar un cambio pasa a “pendiente de reconfirmar”.',
    commitMsg: '¿Qué cambió? (mensaje del commit)', commitBox: 'commit en cam-docs', saved: 'Guardado', savedCommitted: 'Guardado y commit hecho',
    nothingToCommit: 'Guardado (nada que commitear)', confirmedToast: 'Confirmada', commentSaved: 'Comentario guardado',
    translation: 'traducción', newTitle: 'Título', newPath: 'seccion/pagina.md (p. ej. guides/onboarding.md)',
    noDocs: 'Aún no hay documentación', noDocsHelp: 'Lanza la siguiente unidad desde el asistente de Camarón, o crea una página.',
    noMatch: 'Ninguna página coincide.', results: 'Resultados de', noResults: 'Ninguna página lo menciona.',
    reviewTitle: 'Revisión y estado', planUnits: 'Plan {done}/{total} unidades · {pages} páginas',
    waiting: 'Esperando a un humano', allConfirmed: 'Nada — todo confirmado.', changeRequests: 'Peticiones de cambio sin aplicar',
    none: 'Ninguna.', codeChanged: 'Código cambiado desde la última actualización de la doc', allDocumented: 'Todos los repos documentados en su commit actual.',
    askAgent: 'Pide a un agente: “actualiza la doc con los últimos cambios” (skill cam-docs-update).', checks: 'Comprobaciones', allPass: 'Todo correcto.',
    files: 'ficheros', rebuild: '↻ Regenerar', build: 'Generar', builtAt: 'generado {when}', stale: 'desactualizado — la fuente cambió desde entonces',
    notBuilt: 'Aún no generado.', noC4: 'Aún no hay modelo C4 — la unidad arch-system escribe docs/architecture/*.c4.',
    noGraph: 'Aún no hay grafo de código.', allRepos: 'Todos los repos (fusionado)', openTab: 'Abrir en otra pestaña',
    views: 'Vistas', 'kind.system': 'Sistema', 'kind.element': 'Contenedores y componentes', 'kind.dynamic': 'Flujos',
    'kind.deployment': 'Despliegue', explorer: 'Explorador completo', openExplorer: 'Abrir en el explorador', readFlow: 'Leer el flujo',
    viewIn: 'Abrir en Arquitectura', c4Missing: 'El diagrama interactivo aún no está generado.', c4Unavailable: 'Los diagramas interactivos necesitan un build C4 más reciente: regenéralo.',
    diagram: 'Diagrama interactivo: pulsa un elemento para explorarlo',
    wikisHelp: 'OpenWiki escribe una wiki por repo (cam-docs/wikis/<repo>/), con cada afirmación anclada a un fichero y línea del código.',
    noWiki: 'sin wiki', pages: '{n} páginas', updated: 'actualizada {when}', unit: 'unidad del plan', read: 'Leer', graph: 'Grafo',
    generate: 'Generar wiki', update: 'Actualizar wiki', via: 'con', notCloned: 'sin clonar', linkedFrom: 'Enlazada desde',
    wikiPages: 'Páginas', allWikis: 'Todas las wikis', noWikiPages: 'Este repo aún no tiene páginas de wiki.', readPages: 'Leer las páginas',
    wikiOld: 'Escrita con el alcance antiguo, más escueto. Actualízala para tener una wiki completa (módulos, APIs, configuración, operación…).',
    graphBuilding: 'Generando el grafo de la wiki…', graphFailed: 'No se pudo generar el grafo de la wiki: lee las páginas.',
    notChosen: 'sin wiki para este repo (elige repos en el asistente → Wikis)', needBrief: 'antes ejecuta su unidad repo-brief (escribe INSTRUCTIONS.md)',
    noEngine: 'OpenWiki aún no puede lanzarse desde aquí: guarda una clave de proveedor una vez con `openwiki auth configure openai` (o anthropic, gemini, openrouter) en una terminal, o instala Claude Code / Codex para que la escriba un agente.',
    running: 'en curso…', done: 'hecho', failed: 'falló', jobStarted: 'Lanzado: {label}',
    readOnly: 'Portal de solo lectura (exportado). Para editar, confirmar o generar wikis en local ejecuta <code>camaron up</code>.',
    unreachable: 'No se puede conectar con el servidor de la doc', error: 'Error', justNow: 'ahora mismo', notFound: 'Página no encontrada',
  },
};

let T = { docs: [], langs: [], codeGraphs: [], engines: [], repos: [], sections: [], views: [], summary: {} };
let BY_PATH = {};
let WIKIS = null;
let VIEWERS = null;
let SEARCH_INDEX = null;
const store = { get: (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } },
                set: (k, v) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } } };
let lang = store.get('cam-lang');           // '' = English (canonical docs); otherwise a translation code
const ui = () => I18N[lang] || I18N.en;
const t = (k, vars = {}) => (ui()[k] ?? I18N.en[k] ?? k).replace(/\{(\w+)\}/g, (_, v) => vars[v] ?? '');
const has = (k) => (ui()[k] ?? I18N.en[k]) !== undefined;
const ago = (sec) => {
  if (!sec) return '';
  const d = new Date(sec * 1000);
  return (Date.now() - d) < 60000 ? t('justNow') : d.toLocaleString(lang || 'en', { dateStyle: 'medium', timeStyle: 'short' });
};
const sectionLabel = (name) => (has('sec.' + name) ? t('sec.' + name) : name.replace(/[-_]/g, ' ').replace(/^./, (c) => c.toUpperCase()));

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

async function loadTree() {
  T = await api('tree');
  T.sections ||= [];
  T.views ||= [];
  BY_PATH = Object.fromEntries(T.docs.map((d) => [d.path, { ...d, space: d.space || 'docs' }]));
  T.docs = Object.values(BY_PATH);
  WIKIS = null;
  VIEWERS = null;
  if (!T.langs.includes(lang)) lang = '';
  document.title = `${T.project} — Camarón`;
  $('#project').textContent = T.project;
  const s = T.summary;
  $('#summary').textContent = `✅ ${s.confirmed} · ✨ ${s.draft} · ⚠️ ${s['needs-reconfirm']}` + (T.feedback ? ` · ✏️ ${T.feedback}` : '');
}

async function loadWikis() { WIKIS ||= await api('wikis'); return WIKIS; }
async function loadViewers() { VIEWERS ||= await api('viewers'); return VIEWERS; }

// A page's route: wiki pages live in their own space, everything else under Docs.
function hrefFor(path, anchor) {
  const a = anchor ? '::' + anchor : '';
  if (BY_PATH[path]?.space === 'wiki') {
    const [, repo, ...rest] = path.split('/');
    return `#/wiki/${repo}/${rest.join('/')}${a}`;
  }
  return `#/docs/${path}${a}`;
}

function toast(msg) {
  const el = $('#toast');
  el.textContent = msg; el.hidden = false;
  clearTimeout(toast.h); toast.h = setTimeout(() => { el.hidden = true; }, 3500);
}

// ---------- theme: follows the OS until the reader picks one ----------
const systemDark = () => matchMedia('(prefers-color-scheme: dark)').matches;
const isDark = () => (document.documentElement.dataset.theme || (systemDark() ? 'dark' : 'light')) === 'dark';
function applyTheme() {
  const pick = store.get('cam-theme');
  if (pick) document.documentElement.dataset.theme = pick; else delete document.documentElement.dataset.theme;
  $('#theme').textContent = isDark() ? '☀️' : '🌙';
  if (window.mermaid) mermaid.initialize({ startOnLoad: false, theme: isDark() ? 'dark' : 'neutral', securityLevel: 'strict',
    fontFamily: 'ui-sans-serif, system-ui, -apple-system, "Segoe UI", sans-serif' });
  $$('likec4-view').forEach((v) => v.setAttribute('color-scheme', isDark() ? 'dark' : 'light'));
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

async function startBuild(what, repo, btn, logEl, onEnd) {
  btn.disabled = true;
  try {
    watchJob(await api('build', {}, { what, repo }), logEl, onEnd || (async () => { await loadTree(); route(); }));
  } catch (e) { toast(e.message); btn.disabled = false; }
}
