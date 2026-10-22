// The portal server's API (lib/serve.py), relative so the app also works under a sub-path. Mutations need the
// X-Camarones header, which a cross-site page cannot send.
export const STATIC = document.querySelector('meta[name="cam-mode"]')?.content === 'static'

export async function getJSON(path) {
  const res = await fetch(`api/${path}`, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error((await res.json().catch(() => ({}))).error || `${path}: ${res.status}`)
  return res.json()
}

export async function postJSON(path, body) {
  const res = await fetch(`api/${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Camarones': '1' },
    body: JSON.stringify(body || {}),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(data.error || `${path}: ${res.status}`)
  return data
}
