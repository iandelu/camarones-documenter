'use strict'
// Pure helpers of the desktop app's main process: no Electron, no I/O, so `node --test` checks them on every OS.
const path = require('node:path')

// A join token from the shell that started the app is not inherited: only the join the person gave one gets it. The
// same for a portal token: only the project server the app starts gets one, its own.
const NOT_FOR_CHILDREN = ['CAMARONES_APP_TOKEN', 'CAMARONES_ROOT', 'ELECTRON_RUN_AS_NODE', 'CAMARONES_JOIN_TOKEN',
  'CAMARONES_PORTAL_TOKEN']

const backendArgv = (kit) => [path.join(kit, 'camarones.py'), 'up', '--foreground', '--port', '0']
const cliArgv = (kit, args) => [path.join(kit, 'camarones.py'), ...args]

function cliEnv(env) {
  const out = { ...env, PYTHONUTF8: '1' }
  for (const k of NOT_FOR_CHILDREN) delete out[k]
  return out
}

// portalToken: this session's key for the portal the app opens in the browser (as `camaron up` does): with it that
// portal writes the board; it never unlocks what needs the app token.
const backendEnv = (env, root, token, portalToken) => ({ ...cliEnv(env), CAMARONES_ROOT: root, CAMARONES_APP_TOKEN: token,
  ...(portalToken ? { CAMARONES_PORTAL_TOKEN: portalToken } : {}) })

// lib/serve.py prints {"ready": true, "port": N} as its first line when the app started it.
function parseReady(line) {
  try {
    const r = JSON.parse(line)
    return r && r.ready === true && Number.isInteger(r.port) && r.port > 0 ? r.port : null
  } catch { return null }
}

function sameOrigin(url, origin) {
  try { return new URL(url).origin === origin } catch { return false }
}

// The web, and a doc page's source in the reader's editor (portal/app/src/views/sources.js): only the "open this file"
// form of each editor, never another handler of its scheme.
const EDITOR = /^(?:(?:vscode|cursor|windsurf|vscodium):\/\/file\/|(?:idea|webstorm|pycharm):\/\/open\?file=)/
function externalOk(url) {
  try { return ['http:', 'https:'].includes(new URL(url).protocol) || EDITOR.test(url) } catch { return false }
}

// The start screen's CLI calls. A name that looks like an option is dropped (the CLI then uses the folder's name).
const inspectArgs = (dir) => ['projects', '--inspect', dir, '--json']
const adoptArgs = (dir, name) => ['projects', '--adopt', dir, '--json',
  ...(typeof name === 'string' && name.trim() && !name.trim().startsWith('-') ? ['--name', name.trim()] : [])]
const gitInitArgs = (dir) => ['projects', '--git-init', dir, '--json']
const joinArgs = (url, dir) => ['join', url, dir, '--no-open']

// A folder the page hands back: an absolute path (what the folder dialog gives), never an option or a relative one.
const folderArg = (dir) => typeof dir === 'string' && dir.length > 0 && path.isAbsolute(dir)

// The token for a private cam-docs repo goes in the child's environment, never on its command line.
function joinEnv(env, token) {
  const out = cliEnv(env)
  if (typeof token === 'string' && token.trim()) out.CAMARONES_JOIN_TOKEN = token.trim()
  return out
}

// `join --no-open` explains a refused access as one JSON line on stdout: {error, host, detail}; a cam-docs in that
// folder that belongs to something else is {error: "taken", detail}.
const JOIN_REASONS = ['auth', 'denied', 'not-found', 'network', 'unknown', 'taken']
function joinFailure(out) {
  const r = lastJson(out)
  if (!r || typeof r.error !== 'string') return null
  return { error: JOIN_REASONS.includes(r.error) ? r.error : 'unknown', host: String(r.host || ''), detail: String(r.detail || '') }
}

// The CLI's own error: its last stderr line, without the ✖.
function errLine(err) {
  const lines = String(err || '').split(/\r?\n/).map((l) => l.trim()).filter(Boolean)
  return lines.length ? lines[lines.length - 1].replace(/^✖\s*/, '') : ''
}

// Why `projects --adopt --json` refused: its stdout code (taken: a cam-docs there belongs to something else; home: the
// folder is home or a filesystem root; no-git: code without a repository). Anything else is a folder it can't use.
// The CLI's text is never parsed.
const ADOPT_REASONS = ['taken', 'home', 'no-git']
function adoptError(out) {
  const code = (lastJson(out) || {}).error
  return ADOPT_REASONS.includes(code) ? code : 'folder'
}

// Windows has no process groups to signal: taskkill /T takes the server and the jobs it started. Elsewhere the
// backend leads its own group (spawned detached) and main.cjs signals the group.
const killCommand = (platform, pid) => (platform === 'win32' ? ['taskkill', ['/PID', String(pid), '/T', '/F']] : null)

const windowArgs = (token, origin) => [`--camaron-token=${token}`, `--camaron-origin=${origin}`]

function readArgs(argv) {
  const get = (k) => (argv.find((a) => a.startsWith(`--camaron-${k}=`)) || '').slice(`--camaron-${k}=`.length)
  return { token: get('token'), origin: get('origin'), hub: argv.includes('--camaron-hub') }
}

// Whether `p` is `root` or lies under it, after resolving `..`: the app reveals files of its own project only.
function inside(root, p) {
  if (typeof p !== 'string' || typeof root !== 'string') return false
  const rel = path.relative(path.resolve(root), path.resolve(p))
  return rel === '' || (!rel.startsWith('..') && !path.isAbsolute(rel))
}

function lastJson(text) {
  const lines = String(text).trim().split(/\r?\n/).reverse()
  for (const l of lines) {
    try { return JSON.parse(l) } catch { /* progress lines before the answer */ }
  }
  return null
}

// One bar per window: the page's header is the title bar and the system draws its controls over it (Windows and Linux
// in the header's colours, which are the theme's canvas and ink; macOS keeps its traffic lights, centred in the bar).
// The overlay is what makes the titlebar-area-* CSS variables exist, so the header knows where the controls sit.
const BAR = { height: 56, light: { bg: '#fafaf7', ink: '#0a0a0a' }, dark: { bg: '#121211', ink: '#f2f1ec' } }

const barColors = (platform, dark) => {
  if (platform === 'darwin') return null
  const c = dark ? BAR.dark : BAR.light
  return { color: c.bg, symbolColor: c.ink, height: BAR.height }
}

function titleBar(platform, dark) {
  if (platform === 'darwin') {
    return { titleBarStyle: 'hidden', titleBarOverlay: { height: BAR.height }, trafficLightPosition: { x: 18, y: (BAR.height - 16) / 2 } }
  }
  return { titleBarStyle: 'hidden', titleBarOverlay: barColors(platform, dark) }
}

// The shrimp (scripts/icons.py renders both from the portal's favicon): the dock wants the padding of its own grid.
const appIcon = (platform) => (platform === 'darwin' ? 'icon-mac.png' : 'icon.png')

module.exports = { backendArgv, cliArgv, cliEnv, backendEnv, parseReady, sameOrigin, externalOk, killCommand,
  windowArgs, readArgs, inside, lastJson, BAR, barColors, titleBar, appIcon, inspectArgs, adoptArgs, gitInitArgs, joinArgs,
  folderArg, joinEnv, joinFailure, errLine, adoptError }
