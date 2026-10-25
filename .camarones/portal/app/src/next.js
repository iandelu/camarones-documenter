// The app's landing view, Next step (#/next), as data: which unit of the plan to offer. Pure: no React, no fetch.
// `units` are GET pipeline's (lib/serve.py api_pipeline): `available` says the plan lets it start now.

const ORDER = ['doing', 'todo', 'blocked']                 // the one in progress first; a blocked one only to retry it

// The first available unit: the one in progress, else the first to do (the server lists them by phase), else a
// blocked one; null when the plan has nothing left to start.
export function pickNext(units) {
  const open = (units || []).filter((u) => u.available && ORDER.includes(u.status))
  for (const status of ORDER) {
    const u = open.find((x) => x.status === status)
    if (u) return u
  }
  return null
}
