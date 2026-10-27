// The window's theme: the one picked in the portal (cam-theme: same window, same origin, same storage), else the
// system's. The window controls the system draws over the header are told which, so they match (main.cjs paintBar).
const picked = (win) => {
  let pick = ''
  try { pick = win.localStorage.getItem('cam-theme') || '' } catch { /* private mode */ }
  return pick === 'light' || pick === 'dark' ? pick : ''
}
const system = (win) => (win.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')

// What the window shows now, for what a library draws on its own (the canvas), without touching the page.
export const currentTheme = (win = window) => picked(win) || system(win)

export function applyTheme(win = window) {
  const pick = picked(win)
  const root = win.document.documentElement
  if (pick) root.dataset.theme = pick; else delete root.dataset.theme
  const theme = pick || system(win)
  win.camaronApp?.theme?.(theme)
  return theme
}
