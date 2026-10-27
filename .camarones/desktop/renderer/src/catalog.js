// Each section's "All commands": the catalog (lib/catalog.py, read from the CLI's parser) of the zones of its work,
// without the commands its own panels already run. What deletes or moves data goes apart, last.
export const ZONES = { plan: ['generate'], interviews: ['interviews'], team: ['team'], quality: ['check', 'analyze'],
  machine: ['machine'] }
const PANELS = { plan: ['run', 'autopilot', 'docs'], interviews: ['interview'], team: ['remote', 'share', 'trust', 'hooks', 'plugins'],
  quality: ['doctor', 'eval', 'ab', 'inventory', 'health', 'fresh', 'blocks'],
  machine: ['setup', 'config', 'sync', 'detect', 'stack', 'profile', 'self-update', 'repair', 'uninstall'] }

export function others(commands, section) {
  const zones = ZONES[section] || []
  const mine = (commands || []).filter((c) => zones.includes(c.zone) && c.verdict !== 'portal'
    && !(PANELS[section] || []).includes(c.name))
  return { safe: mine.filter((c) => !c.destructive), careful: mine.filter((c) => c.destructive) }
}

// Where the app runs a command (the ⌘K palette goes there): the section whose panel runs it, else the one whose "All
// commands" lists it; none for the portal's own commands or a section this window lacks.
export const inPanel = (c) => Object.values(PANELS).some((names) => names.includes(c.name))
export function sectionFor(c, available) {
  if (c.verdict === 'portal') return null
  const s = Object.keys(PANELS).find((k) => PANELS[k].includes(c.name)) || Object.keys(ZONES).find((k) => ZONES[k].includes(c.zone))
  return s && (!available || available.includes(s)) ? s : null
}
