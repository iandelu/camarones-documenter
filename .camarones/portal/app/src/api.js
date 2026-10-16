// The live portal's API (lib/serve.py). Mutations need the X-Camarones header, which a cross-site page cannot send.
export async function getJSON(path) {
  const res = await fetch(`/api/${path}`, { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`${path}: ${res.status}`)
  return res.json()
}
