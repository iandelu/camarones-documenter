'use strict'
// The hub: projects registered on this machine (`camaron projects`), and creating, joining or adding one. Everything
// goes through window.camaronHub (preload.cjs) to the main process, which runs the CLI.
const S = {
  es: { title: 'Elige un proyecto', lede: 'Tu becario gamba documenta lo que abras aquí: el portal del equipo y el trabajo que corre en tu máquina, en una ventana.',
        projects: 'Proyectos', new: 'Crear proyecto', join: 'Unirse al del equipo', add: 'Añadir carpeta',
        name: 'Nombre del proyecto', from: 'Repo cam-docs del equipo (opcional)', url: 'URL del repo cam-docs del equipo',
        create: 'Crear y elegir carpeta', joinGo: 'Unirse y elegir carpeta', cancel: 'Cancelar', open: 'Abrir',
        missing: 'no está en el disco', empty: 'Aún no hay proyectos en esta máquina. Crea uno, únete al del equipo o añade una carpeta que ya tenga cam-docs.',
        opening: 'Abriendo {name}…', failed: 'No he podido leer los proyectos:', error: 'No ha salido bien:' },
  en: { title: 'Pick a project', lede: 'Your intern shrimp documents whatever you open here: the team\'s portal and the work that runs on your machine, in one window.',
        projects: 'Projects', new: 'Create project', join: 'Join the team\'s', add: 'Add folder',
        name: 'Project name', from: 'The team\'s cam-docs repo (optional)', url: 'URL of the team\'s cam-docs repo',
        create: 'Create and pick a folder', joinGo: 'Join and pick a folder', cancel: 'Cancel', open: 'Open',
        missing: 'not on disk', empty: 'No projects on this machine yet. Create one, join the team\'s or add a folder that already has cam-docs.',
        opening: 'Opening {name}…', failed: 'I could not read the projects:', error: 'That did not work:' },
}
let t = S.es
const $ = (id) => document.getElementById(id)
const hub = window.camaronHub
let mode = ''

function say(text, error = false) {
  $('status').textContent = text
  $('status').classList.toggle('error', error)
}

function busy(on) {
  for (const id of ['new', 'join', 'add', 'go']) $(id).disabled = on
}

async function load() {
  const list = $('list')
  const r = await hub.list()
  list.removeAttribute('aria-busy')
  list.textContent = ''
  if (r.error) return say(`${t.failed} ${r.error}`, true)
  if (!r.projects.length) {
    const li = document.createElement('li')
    li.className = 'empty'
    li.textContent = t.empty
    return list.append(li)
  }
  for (const p of r.projects) {
    const li = document.createElement('li')
    const info = document.createElement('div')
    const name = document.createElement('div')
    name.className = 'name'
    name.textContent = p.name
    const path = document.createElement('div')
    path.className = 'path'
    path.textContent = p.path
    info.append(name, path)
    li.append(info)
    if (p.exists) {
      const b = document.createElement('button')
      b.type = 'button'
      b.className = 'btn ghost'
      b.textContent = t.open
      b.addEventListener('click', () => open(p))
      li.append(b)
    } else {
      const m = document.createElement('span')
      m.className = 'missing'
      m.textContent = t.missing
      li.append(m)
    }
    list.append(li)
  }
}

async function open(p) {
  busy(true)
  say(t.opening.replace('{name}', p.name))
  const r = await hub.open(p.path)
  busy(false)
  if (r && !r.ok) say(`${t.error} ${r.error}`, true)
}

function showForm(which) {
  mode = which
  $('form').hidden = false
  $('field-label').textContent = which === 'new' ? t.name : t.url
  $('from-label').hidden = $('from').hidden = which !== 'new'
  $('from-label').textContent = t.from
  $('go').textContent = which === 'new' ? t.create : t.joinGo
  $('field').value = ''
  $('from').value = ''
  $('field').focus()
}

async function act(fn) {
  busy(true)
  say('')
  try {
    const r = await fn()
    if (r?.error) say(`${t.error} ${r.error}`, true)
    else if (!r?.cancelled) { $('form').hidden = true; await load() }
  } finally { busy(false) }
}

async function main() {
  t = S[await hub.lang()] || S.es
  document.documentElement.lang = t === S.en ? 'en' : 'es'
  $('title').textContent = t.title
  $('lede').textContent = t.lede
  $('h-projects').textContent = t.projects
  $('new').textContent = t.new
  $('join').textContent = t.join
  $('add').textContent = t.add
  $('cancel').textContent = t.cancel
  $('new').addEventListener('click', () => showForm('new'))
  $('join').addEventListener('click', () => showForm('join'))
  $('cancel').addEventListener('click', () => { $('form').hidden = true })
  $('add').addEventListener('click', () => act(() => hub.add()))
  $('form').addEventListener('submit', (e) => {
    e.preventDefault()
    const v = $('field').value.trim()
    if (!v) return
    act(() => (mode === 'new' ? hub.create(v, $('from').value.trim()) : hub.join(v)))
  })
  await load()
}

main()
