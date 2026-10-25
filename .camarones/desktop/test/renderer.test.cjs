'use strict'
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const r = require('../lib/renderer.cjs')

test('a project window loads the app from its own server, on a section', () => {
  assert.equal(r.projectUrl('http://127.0.0.1:5123'), 'http://127.0.0.1:5123/desktop/#/summary')
  assert.equal(r.projectUrl('http://127.0.0.1:5123', 'plan'), 'http://127.0.0.1:5123/desktop/#/plan')
  assert.equal(r.projectUrl('http://127.0.0.1:5123', 'x y'), 'http://127.0.0.1:5123/desktop/#/summary')   // no odd sections
  assert.equal(r.projectUrl('http://127.0.0.1:5123', 'start'), 'http://127.0.0.1:5123/desktop/#/start')   // the first-run wizard
  assert.ok(r.SECTIONS.includes('start'))
})

test('the hub is the same build, from disk', () => {
  assert.equal(r.hubFile('/kit/desktop'), path.join('/kit/desktop', 'renderer-build', 'index.html'))
})

const screen = [{ x: 0, y: 0, width: 1920, height: 1040 }]
test('a window comes back where it was, if that place is still on a screen', () => {
  const saved = { x: 100, y: 80, width: 1200, height: 800 }
  assert.deepEqual(r.bounds(saved, screen), saved)
})

test('a window that was on a screen now gone, or too small, opens at the default size', () => {
  assert.deepEqual(r.bounds({ x: 3000, y: 80, width: 1200, height: 800 }, screen), r.DEFAULT_BOUNDS)
  assert.deepEqual(r.bounds({ x: 10, y: 10, width: 300, height: 200 }, screen), r.DEFAULT_BOUNDS)
  assert.deepEqual(r.bounds(null, screen), r.DEFAULT_BOUNDS)
  assert.deepEqual(r.bounds({ x: 'a' }, screen), r.DEFAULT_BOUNDS)
})

test('the open project is found in the list whatever the spelling of its path', () => {
  assert.equal(r.samePath('/w/a/cam-docs', '/w/a/cam-docs/', 'linux'), true)
  assert.equal(r.samePath('/w/a/cam-docs', '/w/A/cam-docs', 'linux'), false)
  assert.equal(r.samePath('C:\\W\\a\\cam-docs', 'c:/w/a/cam-docs', 'win32'), true)       // Windows ignores case
  assert.equal(r.samePath('/w/a/cam-docs', 42, 'linux'), false)
  const listed = [{ path: '/w/a/cam-docs', exists: true }, { path: '/w/b/cam-docs', exists: true }]
  assert.deepEqual(r.rail(listed, '/w/b/cam-docs/', 'linux').map((p) => p.current), [false, true])
})

test('a second click while a project starts waits for that start instead of starting another server', async () => {
  const inFlight = new Map()
  let starts = 0, done
  const start = () => { starts++; return new Promise((r) => { done = r }) }
  const a = r.oneAtATime(inFlight, '/w/a', start)
  const b = r.oneAtATime(inFlight, '/w/a', start)
  assert.equal(a, b)
  assert.equal(starts, 1)
  done({ ok: true })
  assert.deepEqual(await b, { ok: true })
  assert.equal(inFlight.size, 0)                                        // over: the next click starts again
  r.oneAtATime(inFlight, '/w/a', start)
  assert.equal(starts, 2)
})

test('switching projects only accepts a project the CLI listed and that is on disk', () => {
  const listed = [{ path: '/w/a/cam-docs', exists: true }, { path: '/w/b/cam-docs', exists: false }]
  assert.equal(r.switchable(listed, '/w/a/cam-docs'), true)
  assert.equal(r.switchable(listed, '/w/b/cam-docs'), false)
  assert.equal(r.switchable(listed, '/etc'), false)
  assert.equal(r.switchable(listed, 42), false)
})

test('outsideApp keeps the app and sends the portal out', () => {
  const origin = 'http://127.0.0.1:5000'
  assert.equal(r.outsideApp('http://127.0.0.1:5000/#/review', origin), true)
  assert.equal(r.outsideApp('http://127.0.0.1:5000/raw/x.png', origin), true)
  assert.equal(r.outsideApp('http://127.0.0.1:5000/desktop/#/plan', origin), false)
  assert.equal(r.outsideApp('http://127.0.0.1:5000/desktop', origin), false)
  assert.equal(r.outsideApp('http://127.0.0.1:5000/desktop/assets/x.js', origin), false)
  assert.equal(r.outsideApp('http://127.0.0.1:5000/desktopx/y', origin), true)     // a sibling path, not the app
  assert.equal(r.outsideApp('http://127.0.0.1:6000/#/', origin), false)            // another origin: the external rule's
  assert.equal(r.outsideApp('not a url', origin), false)
})
