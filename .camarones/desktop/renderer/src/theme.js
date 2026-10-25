// The window's theme: the one picked in the portal (cam-theme: same window, same origin, same storage), else the
// system's. The window controls the system draws over the header are told which, so they match (main.cjs paintBar).
export function applyTheme(win = window) {
  let pick = ''
  try { pick = win.localStorage.getItem('cam-theme') || '' } catch { /* private mode */ }
  if (pick !== 'light' && pick !== 'dark') pick = ''
  const root = win.document.documentElement
  if (pick) root.dataset.theme = pick; else delete root.dataset.theme
  const theme = pick || (win.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
  win.camaronApp?.theme?.(theme)
  return theme
}
