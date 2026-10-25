'use strict'
// Camarón's desktop app, main process. It only runs processes and windows: every project window is served by that
// project's own server (lib/serve.py, started here with a fresh token): the app's UI at /desktop/ (desktop/renderer),
// the portal at /, so the app, the portal, the Taller and the CLI are the same code. The hub (the same UI, from disk)
// lists, creates and joins projects through the CLI (`projects`, `new`, `join` with --no-open).
// Started by `camaron app` (lib/desktop.py), which passes the interpreter and kit to call back.
const { app, BrowserWindow, Menu, dialog, ipcMain, screen, session, shell } = require('electron')
const { spawn, spawnSync } = require('node:child_process')
const crypto = require('node:crypto')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const readline = require('node:readline')
const core = require('./lib/core.cjs')
const renderer = require('./lib/renderer.cjs')

const KIT = process.env.CAMARONES_KIT || path.resolve(__dirname, '..')
const PY = process.env.CAMARONES_PY || (process.platform === 'win32' ? 'python' : 'python3')
const PRELOAD = path.join(__dirname, 'preload.cjs')
const projects = new Map()           // docs root → { win, proc, origin }
let hub = null

function lang() {
  try { return JSON.parse(fs.readFileSync(path.join(os.homedir(), '.camarones.json'), 'utf8')).lang === 'en' ? 'en' : 'es' } catch { return 'es' }
}

const L = {
  es: { projects: 'Proyectos…', browser: 'Abrir en el navegador', startFailed: 'No he podido arrancar el servidor del proyecto',
        notProject: 'Esa carpeta no es un proyecto de Camarón', pickParent: 'Carpeta donde crear el proyecto',
        pickJoin: 'Carpeta donde traer el cam-docs del equipo', pickProject: 'Carpeta del proyecto (o su cam-docs)' },
  en: { projects: 'Projects…', browser: 'Open in the browser', startFailed: 'I could not start the project\'s server',
        notProject: 'That folder is not a Camarón project', pickParent: 'Folder to create the project in',
        pickJoin: 'Folder to bring the team\'s cam-docs into', pickProject: 'The project folder (or its cam-docs)' },
}
const s = (k) => L[lang()][k]

// The CLI as a child process: resolves to its exit code and output; never through a shell.
function cli(args, { cwd } = {}) {
  return new Promise((resolve) => {
    const pr = spawn(PY, core.cliArgv(KIT, args), { cwd: cwd || os.homedir(), env: core.cliEnv(process.env), windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'] })
    let out = '', err = ''
    pr.stdout.on('data', (d) => { out += d })
    pr.stderr.on('data', (d) => { err += d })
    pr.on('error', (e) => resolve({ code: -1, out, err: String(e) }))
    pr.on('close', (code) => resolve({ code, out, err }))
  })
}

function killTree(pr) {
  if (!pr || pr.exitCode !== null) return
  const k = core.killCommand(process.platform, pr.pid)
  if (k) { spawnSync(k[0], k[1], { windowsHide: true }); return }
  try { process.kill(-pr.pid, 'SIGTERM') } catch { pr.kill('SIGTERM') }
}

// Every window: no navigation away from its own origin, no pop-ups to other sites, no permissions (camera, …).
function guard(win, origin) {
  const wc = win.webContents
  const leave = (url) => { if (core.externalOk(url)) shell.openExternal(url) }
  wc.on('will-navigate', (e, url) => { if (!origin || !core.sameOrigin(url, origin)) { e.preventDefault(); leave(url) } })
  wc.setWindowOpenHandler(({ url }) => (origin && core.sameOrigin(url, origin) ? { action: 'allow' } : (leave(url), { action: 'deny' })))
}

function windowOptions(extraArgs) {
  return { ...renderer.DEFAULT_BOUNDS, minWidth: renderer.MIN.width, minHeight: renderer.MIN.height, title: 'camarón', show: false,
    backgroundColor: '#fafaf7',
    webPreferences: { preload: PRELOAD, contextIsolation: true, sandbox: true, nodeIntegration: false,
      webSecurity: true, spellcheck: false, additionalArguments: extraArgs } }
}

// Where the project window was last time, if that place is still on a screen (Electron's own folder for this app).
const BOUNDS = () => path.join(app.getPath('userData'), 'window.json')
function lastBounds() {
  let saved = null
  try { saved = JSON.parse(fs.readFileSync(BOUNDS(), 'utf8')) } catch { /* first run */ }
  return renderer.bounds(saved, screen.getAllDisplays().map((d) => d.workArea))
}
function remember(win) {
  win.on('close', () => { try { fs.writeFileSync(BOUNDS(), JSON.stringify(win.getNormalBounds())) } catch { /* read-only */ } })
}

function openHub() {
  if (hub && !hub.isDestroyed()) { hub.focus(); return }
  hub = new BrowserWindow({ ...windowOptions(['--camaron-hub']), width: 860, height: 640 })
  guard(hub, null)
  hub.once('ready-to-show', () => hub.show())
  hub.on('closed', () => { hub = null })
  hub.loadFile(renderer.hubFile(__dirname))
}

function waitReady(pr) {
  return new Promise((resolve, reject) => {
    let err = ''
    const timer = setTimeout(() => reject(new Error(err.trim() || 'timeout')), 60000)
    pr.stderr.on('data', (d) => { err = (err + d).slice(-4000) })
    const rl = readline.createInterface({ input: pr.stdout })
    rl.once('line', (line) => {
      clearTimeout(timer)
      const port = core.parseReady(line)
      if (port) resolve(port); else reject(new Error(err.trim() || line))
    })
    pr.once('exit', (code) => { clearTimeout(timer); reject(new Error(err.trim() || `exit ${code}`)) })
  })
}

// replace: the window that asked to show this project instead (the rail); the new one takes its place and size.
const starting = new Map()           // docs root → its start in progress (a second click waits for it)
const openProject = (root, opts) => renderer.oneAtATime(starting, root, () => startProject(root, opts))

async function startProject(root, { replace } = {}) {
  const open = projects.get(root)
  if (open && !open.win.isDestroyed()) { open.win.focus(); return { ok: true } }
  const token = crypto.randomBytes(24).toString('hex')
  // cwd outside the project: Windows cannot delete a folder a process works in, and `uninstall` runs from here
  const pr = spawn(PY, core.backendArgv(KIT), { cwd: os.homedir(), env: core.backendEnv(process.env, root, token),
    windowsHide: true, detached: process.platform !== 'win32', stdio: ['ignore', 'pipe', 'pipe'] })
  let port
  try { port = await waitReady(pr) } catch (e) {
    killTree(pr)
    dialog.showErrorBox(s('startFailed'), String(e.message || e))
    return { ok: false, error: String(e.message || e) }
  }
  const origin = `http://127.0.0.1:${port}`
  const place = replace && !replace.isDestroyed() ? replace.getNormalBounds() : lastBounds()
  const win = new BrowserWindow({ ...windowOptions(core.windowArgs(token, origin)), ...place })
  if (replace && !replace.isDestroyed() && replace.isMaximized()) win.maximize()
  guard(win, origin)
  remember(win)
  projects.set(root, { win, proc: pr, origin })
  win.once('ready-to-show', () => win.show())
  win.on('closed', () => { killTree(pr); projects.delete(root) })
  pr.on('exit', () => { if (!win.isDestroyed()) win.close() })
  await win.loadURL(renderer.projectUrl(origin))
  if (hub && !hub.isDestroyed()) hub.close()
  if (replace && !replace.isDestroyed()) replace.close()      // its server stops with it
  return { ok: true }
}

const fromHub = (e) => hub && !hub.isDestroyed() && e.sender === hub.webContents
const projectOf = (e) => [...projects.entries()].find(([, p]) => !p.win.isDestroyed() && e.sender === p.win.webContents)
const fromProject = (e) => !!projectOf(e)

async function pickFolder(title) {
  const r = await dialog.showOpenDialog(hub, { title, properties: ['openDirectory', 'createDirectory'] })
  return r.canceled ? null : r.filePaths[0]
}

function handlers() {
  const onHub = (name, fn) => ipcMain.handle(name, (e, arg) => (fromHub(e) ? fn(arg) : null))
  onHub('hub:lang', () => lang())
  onHub('hub:list', async () => {
    const r = await cli(['projects', '--json'])
    if (r.code !== 0) return { error: r.err.trim() || `exit ${r.code}` }
    return { projects: JSON.parse(r.out) }
  })
  onHub('hub:open', (root) => (typeof root === 'string' ? openProject(root) : null))
  onHub('hub:add', async () => {
    const dir = await pickFolder(s('pickProject'))
    if (!dir) return { cancelled: true }
    const r = await cli(['projects', '--add', dir, '--json'])
    return r.code === 0 ? { project: core.lastJson(r.out) } : { error: r.err.trim() || s('notProject') }
  })
  onHub('hub:new', async ({ name, from } = {}) => {
    if (typeof name !== 'string' || !name.trim() || name.startsWith('-')) return { error: 'name' }
    const dir = await pickFolder(s('pickParent'))
    if (!dir) return { cancelled: true }
    const args = ['new', name.trim(), ...(from && !String(from).startsWith('-') ? ['--from', String(from)] : []), '--no-open']
    const r = await cli(args, { cwd: dir })
    const made = r.code === 0 && core.lastJson(r.out)
    return made ? openProject(made.path) : { error: r.err.trim() || `exit ${r.code}` }
  })
  onHub('hub:join', async ({ url } = {}) => {
    if (typeof url !== 'string' || !url.trim() || url.startsWith('-')) return { error: 'url' }
    const dir = await pickFolder(s('pickJoin'))
    if (!dir) return { cancelled: true }
    const r = await cli(['join', url.trim(), dir, '--no-open'])
    const made = r.code === 0 && core.lastJson(r.out)
    return made ? openProject(made.path) : { error: r.err.trim() || `exit ${r.code}` }
  })
  ipcMain.handle('app:hub', (e) => (fromProject(e) ? openHub() : null))
  // The rail: this machine's projects, the window's own marked; switching starts that project's server in its place.
  const listed = async () => {
    const r = await cli(['projects', '--json'])
    return r.code === 0 ? JSON.parse(r.out) : null
  }
  ipcMain.handle('app:projects', async (e) => {
    const [root] = projectOf(e) || []
    if (!root) return null
    const all = await listed()
    return all ? { projects: renderer.rail(all, root) } : { error: 'projects' }
  })
  ipcMain.handle('app:switch', async (e, target) => {
    const p = projectOf(e)
    if (!p) return null
    if (renderer.samePath(p[0], target)) return { ok: true }
    if (!renderer.switchable(await listed(), target)) return { error: 'project' }
    return openProject(target, { replace: p[1].win })
  })
  ipcMain.handle('app:external', (e, url) => (fromProject(e) && core.externalOk(url) ? shell.openExternal(url) : null))
  // After `self-update`: start again on the kit's new code (the backends go first; app.exit skips before-quit).
  ipcMain.handle('app:relaunch', (e) => {
    if (!fromProject(e)) return null
    for (const p of projects.values()) killTree(p.proc)
    app.relaunch()
    app.exit(0)
    return true
  })
  // A file of this window's project in the system file manager (the exported questionnaire, a report…).
  ipcMain.handle('app:reveal', (e, file) => {
    const [root] = projectOf(e) || []
    if (!root || !core.inside(path.dirname(root), file) || !fs.existsSync(file)) return false
    shell.showItemInFolder(path.resolve(file))
    return true
  })
  // Files the person picks to hand to a CLI command (answers to import): only their paths go back to the page.
  ipcMain.handle('app:pick', async (e, kind) => {
    const p = projectOf(e)
    if (!p) return []
    const filters = kind === 'answers' ? [{ name: 'Answers', extensions: ['json', 'yaml', 'yml', 'md'] }] : []
    const r = await dialog.showOpenDialog(p[1].win, { properties: ['openFile', 'multiSelections'], filters })
    return r.canceled ? [] : r.filePaths
  })
}

function menu() {
  const current = () => [...projects.values()].find((p) => p.win === BrowserWindow.getFocusedWindow())
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { label: 'camarón', submenu: [
      { label: s('projects'), accelerator: 'CmdOrCtrl+Shift+O', click: openHub },
      { label: s('browser'), click: () => { const p = current(); if (p) shell.openExternal(`${p.origin}/`) } },
      { type: 'separator' }, { role: 'quit' }] },
    { role: 'editMenu' }, { role: 'viewMenu' }, { role: 'windowMenu' },
  ]))
}

if (!app.requestSingleInstanceLock()) {
  app.quit()
} else {
  app.on('second-instance', () => openHub())
  app.whenReady().then(() => {
    session.defaultSession.setPermissionRequestHandler((_wc, _perm, done) => done(false))
    handlers()
    menu()
    const root = process.env.CAMARONES_ROOT
    if (root && fs.existsSync(root)) openProject(root).then((r) => { if (!r.ok) openHub() }); else openHub()
  })
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) openHub() })
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
  app.on('before-quit', () => { for (const p of projects.values()) killTree(p.proc) })
}
