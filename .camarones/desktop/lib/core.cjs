'use strict'
// Pure helpers of the desktop app's main process: no Electron, no I/O, so `node --test` checks them on every OS.
const path = require('node:path')

const NOT_FOR_CHILDREN = ['CAMARONES_APP_TOKEN', 'CAMARONES_ROOT', 'ELECTRON_RUN_AS_NODE']

const backendArgv = (kit) => [path.join(kit, 'camarones.py'), 'up', '--foreground', '--port', '0']
const cliArgv = (kit, args) => [path.join(kit, 'camarones.py'), ...args]

function cliEnv(env) {
  const out = { ...env, PYTHONUTF8: '1' }
  for (const k of NOT_FOR_CHILDREN) delete out[k]
  return out
}

const backendEnv = (env, root, token) => ({ ...cliEnv(env), CAMARONES_ROOT: root, CAMARONES_APP_TOKEN: token })

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

function externalOk(url) {
  try { return ['http:', 'https:'].includes(new URL(url).protocol) } catch { return false }
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

module.exports = { backendArgv, cliArgv, cliEnv, backendEnv, parseReady, sameOrigin, externalOk, killCommand,
  windowArgs, readArgs, inside, lastJson, BAR, barColors, titleBar }
