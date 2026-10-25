'use strict'
// Pure helpers for the app's own UI (desktop/renderer, built into renderer-build): where each window loads it from,
// where a window comes back, which project a window may switch to. No Electron, no I/O: `node --test` on every OS.
const path = require('node:path')

const SECTIONS = ['summary', 'plan', 'interviews', 'team', 'quality', 'docs', 'machine', 'kitdev']

// A project's window: the app served by that project's own server (same origin as its API, the token as the key).
const projectUrl = (origin, section = 'summary') => `${origin}/desktop/#/${SECTIONS.includes(section) ? section : 'summary'}`

// No project open: the same build, from the kit's folder.
const hubFile = (desktopDir) => path.join(desktopDir, 'renderer-build', 'index.html')

const DEFAULT_BOUNDS = { width: 1280, height: 860 }
const MIN = { width: 720, height: 520 }

// The saved place of the window, if it still fits on one of the screens (workAreas: [{x, y, width, height}]) and is
// not smaller than the window allows; otherwise the default size, centred by the system.
function bounds(saved, workAreas) {
  const ok = saved && ['x', 'y', 'width', 'height'].every((k) => Number.isFinite(saved[k]))
  if (!ok || saved.width < MIN.width || saved.height < MIN.height) return DEFAULT_BOUNDS
  const cx = saved.x + saved.width / 2, cy = saved.y + saved.height / 2
  const on = (workAreas || []).some((a) => cx >= a.x && cx <= a.x + a.width && cy >= a.y && cy <= a.y + a.height)
  return on ? { x: saved.x, y: saved.y, width: saved.width, height: saved.height } : DEFAULT_BOUNDS
}

// A window asks to show another project: only one `camaron projects` listed, and only if it is on disk.
const switchable = (listed, root) => typeof root === 'string' && (listed || []).some((p) => p.path === root && p.exists)

module.exports = { SECTIONS, projectUrl, hubFile, DEFAULT_BOUNDS, MIN, bounds, switchable }
