'use strict';
// The bridge between the React portal (src/) and what the plain scripts still hold: the docs index, the reader's
// language and the strings (core.js). The views reach them through window.CamaronLegacy.

let CURRENT = '';            // page on screen: a hash change that only moves the anchor just scrolls

// What the zones (src/zones.js) offer: the export, the live server, or the desktop app's window (which also has
// the Taller, where machine work runs).
const MODE = () => (STATIC ? 'static' : RUNS ? 'app' : 'live');

// Calls that re-show the current address (a theme change below) go through the shell, one view at a time.
function route() { return window.CamaronShell ? window.CamaronShell.go() : Promise.resolve(); }

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
  current: () => CURRENT,
  setCurrent: (p) => { CURRENT = p; },
  toast: (m) => toast(m),
  ago: (sec) => ago(sec),
  reload: () => loadTree(),
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
  setLang(l) { lang = l; store.set('cam-lang', l); document.documentElement.lang = l || 'en'; CURRENT = ''; },
  toggleTheme() { store.set('cam-theme', isDark() ? 'light' : 'dark'); applyTheme(); CURRENT = ''; },
};

matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { if (!store.get('cam-theme')) { applyTheme(); CURRENT = ''; route(); } });
