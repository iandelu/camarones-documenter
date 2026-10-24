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

function lastJson(text) {
  const lines = String(text).trim().split(/\r?\n/).reverse()
  for (const l of lines) {
    try { return JSON.parse(l) } catch { /* progress lines before the answer */ }
  }
  return null
}

module.exports = { backendArgv, cliArgv, cliEnv, backendEnv, parseReady, sameOrigin, externalOk, killCommand,
  windowArgs, readArgs, lastJson }
