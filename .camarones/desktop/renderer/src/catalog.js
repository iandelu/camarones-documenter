// Each section's "All commands": the catalog (lib/catalog.py, read from the CLI's parser) of the zones of its work,
// without the commands its own panels already run. What deletes or moves data goes apart, last.
export const ZONES = { plan: ['generate'], interviews: ['interviews'], team: ['team'] }
const PANELS = { plan: ['run', 'autopilot'], interviews: ['interview'], team: ['remote', 'share', 'trust', 'hooks', 'plugins'] }

export function others(commands, section) {
  const zones = ZONES[section] || []
  const mine = (commands || []).filter((c) => zones.includes(c.zone) && c.verdict !== 'portal'
    && !(PANELS[section] || []).includes(c.name))
  return { safe: mine.filter((c) => !c.destructive), careful: mine.filter((c) => c.destructive) }
}
