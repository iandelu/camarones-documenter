'use strict';
// The bridge between the shell (src/shell/Shell.jsx) and what the plain scripts still draw: C4 (c4.js), the code
// map (code.js) and the docs renderer (doc.js). The shell owns the page and the router; it calls these through
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

// ---------- the bridge: the shell (src/shell/Shell.jsx) routes, these views paint ----------
// The address table lives in src/router.js. Calls from these scripts that re-show the current address (after a save,
// a language or audience change) go back through the shell, so one view renders at a time.
function route() { return window.CamaronShell ? window.CamaronShell.go() : Promise.resolve(); }

const VIEWS = { showArch: (...a) => showArch(...a), showCodeTab: (...a) => showCodeTab(...a) };

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
  ago: (sec) => ago(sec),
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
