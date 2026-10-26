'use strict'
// Camarón's desktop app, main process. It only runs processes and windows: every project window is served by that
// project's own server (lib/serve.py, started here with a fresh token): the app's UI at /desktop/ (desktop/renderer),
// the portal at /, so the app, the portal and the CLI are the same code. The hub (the same UI, from disk) lists
// projects, asks what a picked folder is, makes it a project and joins a team's docs, all through the CLI
// (`projects`, `projects --inspect/--adopt/--git-init`, `join --no-open`). The portal is read in the system browser,
// with this session's portal token (like `camaron up`), so it writes the board while the app is open.
// Started by `camaron app` (lib/desktop.py), which passes the interpreter and kit to call back.
const { app, BrowserWindow, Menu, dialog, ipcMain, nativeTheme, screen, session, shell } = require('electron')
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
const projects = new Map()           // docs root → { win, proc, origin, portalToken }
let hub = null

function lang() {
  try { return JSON.parse(fs.readFileSync(path.join(os.homedir(), '.camarones.json'), 'utf8')).lang === 'en' ? 'en' : 'es' } catch { return 'es' }
}

const L = {
  es: { projects: 'Proyectos…', browser: 'Abrir en el navegador', startFailed: 'No he podido arrancar el servidor del proyecto',
        pickFolder: 'La carpeta de tu código, o una vacía', pickJoin: 'Carpeta donde traer el cam-docs del equipo' },
  en: { projects: 'Projects…', browser: 'Open in the browser', startFailed: 'I could not start the project\'s server',
        pickFolder: 'Your code\'s folder, or an empty one', pickJoin: 'Folder to bring the team\'s cam-docs into' },
}
const s = (k) => L[lang()][k]

// The CLI as a child process: resolves to its exit code and output; never through a shell. `env` is merged over the
// default child environment (core.cliEnv): the one way a join token reaches the CLI.
function cli(args, { cwd, env } = {}) {
  return new Promise((resolve) => {
    const pr = spawn(PY, core.cliArgv(KIT, args), { cwd: cwd || os.homedir(), env: { ...core.cliEnv(process.env), ...env }, windowsHide: true,
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

// Every window: no navigation away from its own origin, no pop-ups to other sites, no permissions (camera, …). In a
// project window the portal (same origin, outside /desktop/) is read in the system browser, with the session's portal
// token, and the window stays.
function guard(win, origin, portalToken) {
  const wc = win.webContents
  const leave = (url) => { if (core.externalOk(url)) shell.openExternal(renderer.withPortalToken(url, origin, portalToken)) }
  const stays = (url) => origin && core.sameOrigin(url, origin) && !renderer.outsideApp(url, origin)
  wc.on('will-navigate', (e, url) => { if (!stays(url)) { e.preventDefault(); leave(url) } })
  wc.setWindowOpenHandler(({ url }) => (stays(url) ? { action: 'allow' } : (leave(url), { action: 'deny' })))
}

// The page's header is the title bar (core.titleBar); it starts in the system's theme until the page says its own.
function windowOptions(extraArgs) {
  const dark = nativeTheme.shouldUseDarkColors
  return { ...renderer.DEFAULT_BOUNDS, minWidth: renderer.MIN.width, minHeight: renderer.MIN.height, title: 'camarón', show: false,
    ...core.titleBar(process.platform, dark), backgroundColor: (dark ? core.BAR.dark : core.BAR.light).bg,
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
  const portalToken = crypto.randomBytes(24).toString('hex')      // the browser portal's key: board writes, nothing more
  // cwd outside the project: Windows cannot delete a folder a process works in, and `uninstall` runs from here
  const pr = spawn(PY, core.backendArgv(KIT), { cwd: os.homedir(), env: core.backendEnv(process.env, root, token, portalToken),
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
  guard(win, origin, portalToken)
  remember(win)
  projects.set(root, { win, proc: pr, origin, portalToken })
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
  // Pick a folder: the dialog, then what it is (inspect, which never writes), then the person's Continue (adopt).
  // A refusal comes back as a kind the page words itself (folder | taken | home | no-git) with the CLI's line as detail.
  onHub('hub:pick', async () => {
    const dir = await pickFolder(s('pickFolder'))
    return dir ? { dir } : { cancelled: true }
  })
  onHub('hub:inspect', async (dir) => {
    if (!core.folderArg(dir)) return { error: 'folder', detail: '' }
    const r = await cli(core.inspectArgs(dir))
    const found = r.code === 0 && core.lastJson(r.out)
    return found && found.case ? { found } : { error: 'folder', detail: core.errLine(r.err) || `exit ${r.code}` }
  })
  onHub('hub:adopt', async ({ dir, name } = {}) => {
    if (!core.folderArg(dir)) return { error: 'folder', detail: '' }
    const r = await cli(core.adoptArgs(dir, name))
    const made = r.code === 0 && core.lastJson(r.out)
    if (made && made.path) return openProject(made.path)
    return { error: core.adoptError(r.out), detail: core.errLine(r.err) || `exit ${r.code}` }
  })
  // Code without a git repository: only the person's click on "Initialise git here" gets here, never on its own.
  onHub('hub:gitInit', async (dir) => {
    if (!core.folderArg(dir)) return { error: 'folder', detail: '' }
    const r = await cli(core.gitInitArgs(dir))
    const done = r.code === 0 && core.lastJson(r.out)
    if (done && Array.isArray(done.initialised)) return { initialised: done.initialised }
    const why = core.lastJson(r.out) || {}
    return { error: 'git-init', detail: String(why.detail || '') || core.errLine(r.err) || `exit ${r.code}` }
  })
  // Join: the URL, then where it goes (asked once: a retry with a token passes the same `dir` back). A refused access
  // returns the CLI's reason ({error: auth|denied|not-found|network|unknown|taken, host, detail, dir}); anything else
  // is "failed". The token goes only in the child's environment.
  onHub('hub:join', async ({ url, token, dir } = {}) => {
    if (typeof url !== 'string' || !url.trim() || url.trim().startsWith('-')) return { error: 'url' }
    if (dir != null && !core.folderArg(dir)) return { error: 'folder' }
    const into = dir || await pickFolder(s('pickJoin'))
    if (!into) return { cancelled: true }
    const r = await cli(core.joinArgs(url.trim(), into), { env: core.joinEnv(process.env, token) })
    const made = r.code === 0 && core.lastJson(r.out)
    if (made && made.path) return openProject(made.path)
    const why = core.joinFailure(r.out) || { error: 'failed', host: '', detail: core.errLine(r.err) || `exit ${r.code}` }
    return { ...why, dir: into }
  })
  ipcMain.handle('app:hub', (e) => (fromProject(e) ? openHub() : null))
  ipcMain.handle('app:lang', (e) => (fromProject(e) ? lang() : null))     // a project window speaks the hub's language
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
  // The portal's light / dark (it can differ from the system's): the controls over its header follow it.
  ipcMain.handle('app:theme', (e, theme) => {
    const p = projectOf(e)
    if (p && ['light', 'dark'].includes(theme)) paintBar(p[1].win, theme === 'dark')
  })
  // With no menu bar on screen (Windows, Linux), the header's button opens the app menu under it.
  ipcMain.handle('app:menu', (e, at) => {
    const p = projectOf(e)
    if (!p) return
    const x = Math.round(Number(at?.x)) || 0, y = Math.round(Number(at?.y)) || 0
    Menu.getApplicationMenu()?.popup({ window: p[1].win, x, y })
  })
  ipcMain.handle('app:external', (e, url) => {
    const [, p] = projectOf(e) || []
    return p && core.externalOk(url) ? shell.openExternal(renderer.withPortalToken(url, p.origin, p.portalToken)) : null
  })
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

function paintBar(win, dark) {
  const colors = core.barColors(process.platform, dark)
  if (colors && !win.isDestroyed()) win.setTitleBarOverlay(colors)
}

function menu() {
  const current = () => [...projects.values()].find((p) => p.win === BrowserWindow.getFocusedWindow())
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform === 'darwin' ? [{ role: 'appMenu' }] : []),
    { label: 'camarón', submenu: [
      { label: s('projects'), accelerator: 'CmdOrCtrl+Shift+O', click: openHub },
      { label: s('browser'), click: () => { const p = current(); if (p) shell.openExternal(renderer.withPortalToken(`${p.origin}/`, p.origin, p.portalToken)) } },
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
    nativeTheme.on('updated', () => { if (hub && !hub.isDestroyed()) paintBar(hub, nativeTheme.shouldUseDarkColors) })
    const root = process.env.CAMARONES_ROOT
    if (root && fs.existsSync(root)) openProject(root).then((r) => { if (!r.ok) openHub() }); else openHub()
  })
  app.on('activate', () => { if (!BrowserWindow.getAllWindows().length) openHub() })
  app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
  app.on('before-quit', () => { for (const p of projects.values()) killTree(p.proc) })
}
