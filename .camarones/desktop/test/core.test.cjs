'use strict'
// The desktop app's pure helpers (lib/core.cjs): command lines, environment, the ready line, which addresses a window
// may load and how a backend's process tree is stopped. Run with `node --test` on macOS, Windows and Linux.
const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const core = require('../lib/core.cjs')

const KIT = path.join(path.sep === '\\' ? 'C:\\' : '/', 'kit', '.camarones')

test('the backend is the portal server on a free port', () => {
  assert.deepEqual(core.backendArgv(KIT), [path.join(KIT, 'camarones.py'), 'up', '--foreground', '--port', '0'])
  assert.deepEqual(core.cliArgv(KIT, ['projects', '--json']), [path.join(KIT, 'camarones.py'), 'projects', '--json'])
})

test('the environment names the project, never leaks a token to the CLI', () => {
  const base = { PATH: 'p', CAMARONES_APP_TOKEN: 'old', CAMARONES_ROOT: '/elsewhere', ELECTRON_RUN_AS_NODE: '1' }
  const cli = core.cliEnv(base)
  assert.equal(cli.PATH, 'p')
  assert.equal(cli.PYTHONUTF8, '1')
  assert.equal(cli.CAMARONES_APP_TOKEN, undefined)
  assert.equal(cli.CAMARONES_ROOT, undefined)
  assert.equal(cli.ELECTRON_RUN_AS_NODE, undefined)
  const be = core.backendEnv(base, '/work/shop/cam-docs', 'tok')
  assert.equal(be.CAMARONES_ROOT, '/work/shop/cam-docs')
  assert.equal(be.CAMARONES_APP_TOKEN, 'tok')
})

test('the ready line gives the port; anything else does not', () => {
  assert.equal(core.parseReady('{"ready": true, "port": 51234}'), 51234)
  assert.equal(core.parseReady('Traceback (most recent call last):'), null)
  assert.equal(core.parseReady('{"ready": false, "port": 1}'), null)
  assert.equal(core.parseReady('{"ready": true, "port": "x"}'), null)
})

test('a window stays on its own server; other addresses open in the browser, only http(s)', () => {
  const origin = 'http://127.0.0.1:51234'
  assert.equal(core.sameOrigin('http://127.0.0.1:51234/#/docs', origin), true)
  assert.equal(core.sameOrigin('http://127.0.0.1:51235/', origin), false)
  assert.equal(core.sameOrigin('http://localhost:51234/', origin), false)
  assert.equal(core.sameOrigin('not a url', origin), false)
  assert.equal(core.externalOk('https://github.com/x'), true)
  assert.equal(core.externalOk('http://example.com'), true)
  assert.equal(core.externalOk('file:///etc/passwd'), false)
  assert.equal(core.externalOk('javascript:alert(1)'), false)
  assert.equal(core.externalOk('smb://server/share'), false)
})

test('stopping a backend stops what it started too', () => {
  assert.deepEqual(core.killCommand('win32', 4242), ['taskkill', ['/PID', '4242', '/T', '/F']])
  assert.equal(core.killCommand('linux', 4242), null)
  assert.equal(core.killCommand('darwin', 4242), null)
})

test('the token and origin reach the preload as arguments, and are read back', () => {
  const args = core.windowArgs('tok', 'http://127.0.0.1:9')
  assert.deepEqual(core.readArgs(['electron', ...args]), { token: 'tok', origin: 'http://127.0.0.1:9', hub: false })
  assert.deepEqual(core.readArgs(['electron', '--camaron-hub']), { token: '', origin: '', hub: true })
})

test('the last JSON line of a CLI answer', () => {
  assert.deepEqual(core.lastJson('🦐 cloning…\n{"path": "/a/cam-docs"}\n'), { path: '/a/cam-docs' })
  assert.equal(core.lastJson('no json here'), null)
})

test('a path the app may reveal lies inside the project', () => {
  const root = path.join(KIT, '..', 'shop', 'cam-docs')
  assert.equal(core.inside(root, path.join(root, 'docs', 'interview', 'q.html')), true)
  assert.equal(core.inside(root, root), true)
  assert.equal(core.inside(root, path.join(root, '..', 'secrets.txt')), false)
  assert.equal(core.inside(root, path.join(root + '-evil', 'x')), false)
  assert.equal(core.inside(root, 42), false)
})

test('one bar: the portal header is the title bar, the system controls drawn over it in its colours', () => {
  for (const platform of ['win32', 'linux']) {
    const light = core.titleBar(platform, false)
    assert.equal(light.titleBarStyle, 'hidden')
    assert.deepEqual(light.titleBarOverlay, { color: core.BAR.light.bg, symbolColor: core.BAR.light.ink, height: core.BAR.height })
    assert.equal(light.trafficLightPosition, undefined)
    assert.equal(core.titleBar(platform, true).titleBarOverlay.color, core.BAR.dark.bg)
    assert.deepEqual(core.barColors(platform, true), core.titleBar(platform, true).titleBarOverlay)
  }
  const mac = core.titleBar('darwin', true)
  assert.equal(mac.titleBarStyle, 'hidden')
  assert.deepEqual(mac.titleBarOverlay, { height: core.BAR.height })          // enables the titlebar-area-* CSS variables
  assert.deepEqual(mac.trafficLightPosition, { x: 18, y: (core.BAR.height - 16) / 2 })
  assert.equal(core.barColors('darwin', true), null)                         // the traffic lights keep their own colours
})

test('the bar\'s colours are the theme\'s canvas and ink, light and dark', () => {
  const tokens = fs.readFileSync(path.join(__dirname, '..', '..', 'ui', 'theme', 'tokens.css'), 'utf8')
  const dark = tokens.slice(tokens.indexOf(':root[data-theme="dark"]'))
  const value = (css, name) => css.match(new RegExp(`--color-${name}:\\s*(#[0-9a-f]{6})`, 'i'))[1].toLowerCase()
  assert.equal(core.BAR.light.bg, value(tokens, 'canvas'))
  assert.equal(core.BAR.light.ink, value(tokens, 'ink'))
  assert.equal(core.BAR.dark.bg, value(dark, 'canvas'))
  assert.equal(core.BAR.dark.ink, value(dark, 'ink'))
  assert.equal(core.BAR.height, 56)                                           // the portal's --top, 3.5rem
})

test('inspectArgs asks the CLI what a folder is', () => {
  const dir = path.join(KIT, '..', 'shop')
  assert.deepEqual(core.inspectArgs(dir), ['projects', '--inspect', dir, '--json'])
})

test('adoptArgs drops a name that looks like an option', () => {
  const dir = path.join(KIT, '..', 'shop')
  assert.deepEqual(core.adoptArgs(dir, 'Shop online'), ['projects', '--adopt', dir, '--json', '--name', 'Shop online'])
  assert.deepEqual(core.adoptArgs(dir, '--json'), ['projects', '--adopt', dir, '--json'])
  assert.deepEqual(core.adoptArgs(dir, '-x'), ['projects', '--adopt', dir, '--json'])
})

test('adoptArgs with no name', () => {
  const dir = path.join(KIT, '..', 'shop')
  for (const name of [undefined, null, '', 42]) assert.deepEqual(core.adoptArgs(dir, name), ['projects', '--adopt', dir, '--json'])
})

test('gitInitArgs asks the CLI to init git where the code is', () => {
  const dir = path.join(KIT, '..', 'shop')
  assert.deepEqual(core.gitInitArgs(dir), ['projects', '--git-init', dir, '--json'])
})

test('a folder from the page is an absolute path, nothing else', () => {
  assert.equal(core.folderArg(path.join(KIT, '..', 'shop')), true)
  assert.equal(core.folderArg('shop'), false)
  assert.equal(core.folderArg('--json'), false)
  assert.equal(core.folderArg(''), false)
  assert.equal(core.folderArg(42), false)
})

test('a join token reaches the CLI only in its environment, never inherited', () => {
  const dir = path.join(KIT, '..', 'shop')
  assert.deepEqual(core.joinArgs('https://gitlab.com/shop/cam-docs.git', dir),
    ['join', 'https://gitlab.com/shop/cam-docs.git', dir, '--no-open'])
  const base = { PATH: 'p', CAMARONES_JOIN_TOKEN: 'from-the-shell', CAMARONES_APP_TOKEN: 'x' }
  assert.equal(core.cliEnv(base).CAMARONES_JOIN_TOKEN, undefined)            // only the join that was given one
  assert.equal(core.joinEnv(base, '').CAMARONES_JOIN_TOKEN, undefined)
  assert.equal(core.joinEnv(base, undefined).CAMARONES_JOIN_TOKEN, undefined)
  const env = core.joinEnv(base, '  glpat-123 ')
  assert.equal(env.CAMARONES_JOIN_TOKEN, 'glpat-123')
  assert.equal(env.CAMARONES_APP_TOKEN, undefined)
  assert.equal(env.PATH, 'p')
})

test('why a join failed: the CLI\'s JSON line, or nothing', () => {
  const out = '{"error": "auth", "host": "gitlab.com", "detail": "HTTP Basic: Access denied"}\n'
  assert.deepEqual(core.joinFailure(out), { error: 'auth', host: 'gitlab.com', detail: 'HTTP Basic: Access denied' })
  assert.deepEqual(core.joinFailure('{"error": "weird"}'), { error: 'unknown', host: '', detail: '' })
  assert.equal(core.joinFailure('{"path": "/a/cam-docs", "joined": true}'), null)
  assert.equal(core.joinFailure(''), null)
  // the folder's cam-docs belongs to something else: a stable code, not the CLI's Spanish line
  assert.deepEqual(core.joinFailure('{"error": "taken", "detail": "/x/cam-docs ya existe y no está vacía"}'),
    { error: 'taken', host: '', detail: '/x/cam-docs ya existe y no está vacía' })
})

test('the CLI\'s error line', () => {
  assert.equal(core.errLine('Warning: something\n✖ not a folder: /x\n'), 'not a folder: /x')
  assert.equal(core.errLine(''), '')
})

test('why an adopt was refused: the JSON code on stdout, never the text', () => {
  for (const code of ['taken', 'home', 'no-git']) {
    assert.equal(core.adoptError(`{"error": "${code}", "detail": "/x/cam-docs ya existe y no está vacía"}\n`), code)
  }
  assert.equal(core.adoptError('progress\n{"error": "home", "detail": "d"}\n'), 'home')
  assert.equal(core.adoptError(''), 'folder')                                 // not a folder, unreadable: no JSON
  assert.equal(core.adoptError('/x/cam-docs ya existe y no está vacía'), 'folder')
  assert.equal(core.adoptError('{"error": "other"}'), 'folder')
  assert.equal(core.adoptError('{"error": "git-init"}'), 'folder')
})
