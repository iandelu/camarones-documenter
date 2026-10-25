'use strict'
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const r = require('../lib/renderer.cjs')

test('a project window loads the app from its own server, on a section', () => {
  assert.equal(r.projectUrl('http://127.0.0.1:5123'), 'http://127.0.0.1:5123/desktop/#/summary')
  assert.equal(r.projectUrl('http://127.0.0.1:5123', 'plan'), 'http://127.0.0.1:5123/desktop/#/plan')
  assert.equal(r.projectUrl('http://127.0.0.1:5123', 'x y'), 'http://127.0.0.1:5123/desktop/#/summary')   // no odd sections
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

test('switching projects only accepts a project the CLI listed and that is on disk', () => {
  const listed = [{ path: '/w/a/cam-docs', exists: true }, { path: '/w/b/cam-docs', exists: false }]
  assert.equal(r.switchable(listed, '/w/a/cam-docs'), true)
  assert.equal(r.switchable(listed, '/w/b/cam-docs'), false)
  assert.equal(r.switchable(listed, '/etc'), false)
  assert.equal(r.switchable(listed, 42), false)
})
