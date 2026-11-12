// What a share (env.share, POST /api/sync/share) or a check for news (env.sync_status fetch) says, as a key and its
// vars for each app's own strings. An error git explained (projects.git_failure, plus no-token) gets its reason's
// sentence, with git's own line apart as the detail; anything else keeps its status sentence, as the wizard does.

const OK = ['pushed', 'up-to-date', 'nothing']
const REASONS = ['network', 'auth', 'no-token', 'denied', 'not-found']
const TOKEN = ['auth', 'no-token', 'denied']

export const shareOk = (r) => !!r && OK.includes(r.status)

// git@host:path, scheme://host/path; a local path names itself.
function hostOf(remote) {
  const ssh = /^[\w.+-]+@([^:/]+)[:/]/.exec(remote)
  if (ssh) return ssh[1]
  try { return new URL(remote).hostname || remote } catch { return remote }
}

function reasonSay(r, remote) {
  const host = r.host || hostOf(remote || '')
  return { key: `sy.err.${r.reason}`, vars: { host, url: remote || host }, detail: r.detail || '',
    token: TOKEN.includes(r.reason) && r.host ? r.host : '' }
}

export function shareSay(r, remote = '') {
  if (r?.status === 'error' && REASONS.includes(r.reason)) return reasonSay(r, remote)
  return { key: `sy.${r?.status}`, vars: { detail: r?.detail || '' }, detail: '', token: '' }
}

// null when the check went well or did not run; an empty key when git failed for a reason it did not explain.
export function fetchSay(fetched, remote = '') {
  if (!fetched || fetched.ok) return null
  if (REASONS.includes(fetched.reason)) return reasonSay(fetched, remote)
  return { key: '', vars: {}, detail: fetched.detail || '', token: '' }
}
