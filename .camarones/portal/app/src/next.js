// The app's landing view, Next step (#/next), as data: which unit of the plan to offer, and whether the project has
// documentation yet. Pure: no React, no fetch. `units` are GET pipeline's (lib/serve.py api_pipeline): `available`
// says the plan lets it start now.

// The unit in progress; else the first available one an agent works on (the view offers a session on it); else the
// first available one. A blocked unit only needs a retry, so it comes last. Null when the plan has nothing to start.
export function pickNext(units) {
  const open = (units || []).filter((u) => u.available && ['doing', 'todo', 'blocked'].includes(u.status))
  const ready = open.filter((u) => u.status !== 'blocked')
  return open.find((u) => u.status === 'doing')
    || ready.find((u) => u.runner === 'agent') || ready[0] || open[0] || null
}

// Nothing of the project's own is documented yet (the kit's guides and interview notes do not count): the case where
// the first look from the code, no AI, is the way forward. `tree` is GET tree; legacy/app.js emptyProject() is the twin.
export function isEmptyProject(tree) {
  const kit = new Set(tree.kitGuides || [])
  return !(tree.docs || []).some((d) => d.space === 'docs' && !kit.has(d.path) && d.type !== 'interview') && !(tree.views || []).length
}
