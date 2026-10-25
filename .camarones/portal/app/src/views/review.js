// Review, pure: the queue's filters and counts, and which repos changed since they were documented.

export const FILTERS = ['all', 'draft', 'needs-reconfirm']

export const filterQueue = (queue, f) => (f === 'all' ? queue : queue.filter((r) => r.trust === f))

export const queueCounts = (queue) => Object.fromEntries(FILTERS.map((f) => [f, filterQueue(queue, f).length]))

export const changedRepos = (changes) => Object.entries(changes || {}).filter(([, c]) => c.status !== 'up-to-date')
  .map(([repo, c]) => ({ repo, status: c.status, files: (c.files || []).length }))
