'use strict'
// The hub is the start screen: what do you want to document. Pick a folder (the CLI says what it is, the person
// confirms, it becomes a project), join the team's cam-docs, or open a recent project. Everything goes through
// window.camaronHub (preload.cjs) to the main process, which runs the CLI; the project window takes it from there.
const S = {
  es: {
    title: '¿Qué quieres documentar?', lede: 'Elige por dónde empezamos. Lo demás lo vamos viendo juntos, paso a paso.',
    pickTitle: 'Elegir carpeta', pickHelp: 'La carpeta de tu código (un repo o varios), o una vacía si aún no hay código.',
    pick: 'Elegir…',
    joinTitle: 'Unirme a la documentación de mi equipo',
    joinHelp: 'Tu equipo ya tiene un repo `cam-docs`. Pega su URL: es el repo de la documentación, no el del código.',
    join: 'Unirme…', recent: 'Recientes', open: 'Abrir', missing: 'no está en el disco',
    listFailed: 'No he podido leer los proyectos.', opening: 'Abriendo {name}…', looking: 'Mirando la carpeta…',
    openFailed: 'No he podido abrir el proyecto.', back: '← Atrás',
    // join
    urlLabel: 'URL del repo cam-docs del equipo', joinGo: 'Elegir carpeta y unirme', tokenGo: 'Probar con el token',
    cancel: 'Cancelar', joiningNow: 'Conectando con el repo del equipo…', tokenLabel: 'Token de acceso para {host}',
    tokenHelp: 'GitLab: read_repository + write_repository · GitHub: repo. Se guarda en el llavero del sistema, nunca en el proyecto.',
    auth: '{host} pide credenciales y tu git no tiene ninguna que valga. Pega un token de acceso y lo intento otra vez.',
    authAgain: '{host} rechaza ese token. Revisa sus permisos o pega otro.',
    authSsh: 'El repo pide credenciales y tu git no tiene ninguna que valga. Configura tu clave SSH o usa la URL https del repo.',
    denied: '{host} no te deja entrar en ese repo. Pide acceso a tu equipo.',
    'not-found': 'No encuentro ese repo. Revisa la URL y que tu usuario tenga acceso.',
    network: 'No llego a {host}. Revisa la conexión, la VPN o el proxy.',
    unknown: 'No puedo leer ese repo.', failed: 'No he podido unirme a ese repo.', server: 'El servidor',
    // what I found
    foundTitle: 'Lo que he encontrado', badgeCode: 'Código existente', badgeNew: 'Proyecto nuevo', badgeDone: 'Ya documentado',
    umbrella: (n) => (n === 1 ? '1 repo con código' : `${n} repos con código`),
    umbrellaText: 'Los analizo y documento lo que hay.',
    repoTitle: 'Es el repo «{name}»', repoText: 'Creo cam-docs junto a él, en la carpeta padre.',
    siblings: (n) => (n === 1 ? 'Hay 1 repo más junto a él ({names}): puedes sumarlo en el siguiente paso.'
      : `Hay ${n} repos más junto a él ({names}): puedes sumarlos en el siguiente paso.`),
    codeTitle: 'Carpeta con código', codeText: 'Lo analizo y documento lo que hay.',
    noGit: 'No es un repositorio git: lo documento igual, pero sin git no hay historial ni ramas que leer.',
    emptyTitle: 'Carpeta sin código', emptyText: 'Documentamos el diseño antes de programar: dominio y arquitectura objetivo.',
    projectTitle: 'Ya tiene cam-docs', projectText: 'Lo abro tal cual. Si falta preparar esta máquina, sigo con herramientas.',
    more: (n) => `y ${n} más`, and: ' y ',
    name: 'Nombre del proyecto', change: 'Cambiar carpeta', continue: 'Continuar →', preparing: 'Preparando el proyecto…',
    folderBad: 'No puedo usar esa carpeta. Elige otra.',
    taken: 'Esa carpeta ya tiene un cam-docs que no es un proyecto de Camarón. Elige otra carpeta o vacía ese cam-docs.',
  },
  en: {
    title: 'What do you want to document?', lede: 'Pick where we start. We\'ll work out the rest together, one step at a time.',
    pickTitle: 'Pick a folder', pickHelp: 'Your code\'s folder (one repo or several), or an empty one if there\'s no code yet.',
    pick: 'Choose…',
    joinTitle: 'Join my team\'s documentation',
    joinHelp: 'Your team already has a `cam-docs` repo. Paste its URL: it\'s the documentation\'s repo, not the code\'s.',
    join: 'Join…', recent: 'Recent', open: 'Open', missing: 'not on disk',
    listFailed: 'I couldn\'t read the projects.', opening: 'Opening {name}…', looking: 'Looking at the folder…',
    openFailed: 'I couldn\'t open the project.', back: '← Back',
    urlLabel: 'URL of the team\'s cam-docs repo', joinGo: 'Pick a folder and join', tokenGo: 'Try with the token',
    cancel: 'Cancel', joiningNow: 'Connecting to the team\'s repo…', tokenLabel: 'Access token for {host}',
    tokenHelp: 'GitLab: read_repository + write_repository · GitHub: repo. It\'s kept in the OS keychain, never in the project.',
    auth: '{host} asks for credentials and your git has none that work. Paste an access token and I\'ll try again.',
    authAgain: '{host} rejects that token. Check its permissions or paste another one.',
    authSsh: 'The repo asks for credentials and your git has none that work. Set up your SSH key or use the repo\'s https URL.',
    denied: '{host} won\'t let you into that repo. Ask your team for access.',
    'not-found': 'I can\'t find that repo. Check the URL and that your user has access to it.',
    network: 'I can\'t reach {host}. Check the connection, VPN or proxy.',
    unknown: 'I can\'t read that repo.', failed: 'I couldn\'t join that repo.', server: 'The server',
    foundTitle: 'What I found', badgeCode: 'Existing code', badgeNew: 'New project', badgeDone: 'Already documented',
    umbrella: (n) => (n === 1 ? '1 repo with code' : `${n} repos with code`),
    umbrellaText: 'I\'ll analyse them and document what\'s there.',
    repoTitle: 'It\'s the "{name}" repo', repoText: 'I\'ll create cam-docs next to it, in the parent folder.',
    siblings: (n) => (n === 1 ? '1 more repo next to it ({names}): you can add it in the next step.'
      : `${n} more repos next to it ({names}): you can add them in the next step.`),
    codeTitle: 'A folder with code', codeText: 'I\'ll analyse it and document what\'s there.',
    noGit: 'It isn\'t a git repository: I\'ll document it anyway, but without git there\'s no history or branches to read.',
    emptyTitle: 'A folder with no code', emptyText: 'We document the design before writing code: the domain and the target architecture.',
    projectTitle: 'It already has cam-docs', projectText: 'I\'ll open it as it is. If this machine still needs setting up, I\'ll go on with the tools.',
    more: (n) => `and ${n} more`, and: ' and ',
    name: 'Project name', change: 'Change folder', continue: 'Continue →', preparing: 'Preparing the project…',
    folderBad: 'I can\'t use that folder. Pick another one.',
    taken: 'That folder already has a cam-docs that isn\'t a Camarón project. Pick another folder, or empty that cam-docs.',
  },
}
let t = S.es
const $ = (id) => document.getElementById(id)
const hub = window.camaronHub
const fill = (text, vars) => text.replace(/\{(\w+)\}/g, (_, k) => (k in vars ? vars[k] : `{${k}}`))
let found = null                      // {dir, info}: the folder picked and what the CLI says it is
let joinDir = null                    // the folder a join goes into, kept for a retry with a token

// Text with `code` spans, built as nodes (never innerHTML).
function rich(el, text) {
  el.textContent = ''
  text.split('`').forEach((part, i) => {
    if (i % 2) { const c = document.createElement('code'); c.textContent = part; el.append(c) } else if (part) el.append(part)
  })
}

// One status line per screen in the hub's own words, and the CLI's line, when there is one, as small detail text.
function say(where, text, detail = '', error = false) {
  const [st, dt] = { start: ['status', 'detail'], join: ['join-status', 'join-detail'], found: ['found-status', 'found-detail'] }[where]
  $(st).textContent = text
  $(st).classList.toggle('error', error)
  $(dt).textContent = detail || ''
}

function busy(on) {
  for (const b of document.querySelectorAll('button')) b.disabled = on
}

function show(view) {
  for (const id of ['start', 'joining', 'found']) $(id).hidden = id !== view
  window.scrollTo(0, 0)
}

// "api, web, infra and 3 more"
function names(rows, max = 4) {
  const n = rows.map((r) => r.name)
  if (!n.length) return ''
  if (n.length > max) return `${n.slice(0, max).join(', ')} ${t.more(n.length - max)}`
  return n.length === 1 ? n[0] : `${n.slice(0, -1).join(', ')}${t.and}${n[n.length - 1]}`
}

async function load() {
  const list = $('list')
  const r = await hub.list()
  list.removeAttribute('aria-busy')
  list.textContent = ''
  if (!r || r.error) { $('recent').hidden = true; return say('start', t.listFailed, r && r.error, true) }
  $('recent').hidden = !r.projects.length         // first run: nothing recent, the two options are the whole screen
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
  say('start', fill(t.opening, { name: p.name }))
  try {
    const r = await hub.open(p.path)
    if (r && !r.ok) say('start', t.openFailed, r.error, true)
  } finally { busy(false) }
}

// ---------- pick a folder → what I found → adopt ----------
async function pickAndInspect(where) {
  const p = await hub.pick()
  if (!p || p.cancelled) return
  busy(true)
  say(where, t.looking)
  try {
    const r = await hub.inspect(p.dir)
    if (!r || r.error) return say(where, t.folderBad, r && r.detail, true)
    say(where, '')
    showFound(p.dir, r.found)
  } finally { busy(false) }
}

const CARD = {
  umbrella: (f) => ({ badge: ['code', t.badgeCode], title: t.umbrella(f.repos.length),
    text: [names(f.repos), t.umbrellaText].filter(Boolean).join('. ') }),
  repo: (f) => ({ badge: ['code', t.badgeCode], title: fill(t.repoTitle, { name: (f.repos[0] || {}).name || '' }),
    text: t.repoText }),
  code: () => ({ badge: ['code', t.badgeCode], title: t.codeTitle, text: t.codeText }),
  empty: () => ({ badge: ['new', t.badgeNew], title: t.emptyTitle, text: t.emptyText }),
  project: () => ({ badge: ['done', t.badgeDone], title: t.projectTitle, text: t.projectText }),
}

function showFound(dir, info) {
  found = { dir, info }
  const c = (CARD[info.case] || CARD.empty)(info)
  $('f-badge').textContent = c.badge[1]
  $('f-badge').dataset.tone = c.badge[0]
  $('f-title').textContent = c.title
  $('f-text').textContent = c.text
  const sib = info.case === 'repo' ? info.siblings || [] : []
  $('f-siblings').hidden = !sib.length
  $('f-siblings').textContent = sib.length ? fill(t.siblings(sib.length), { names: names(sib) }) : ''
  $('f-warn').hidden = info.warning !== 'no-git'
  $('f-warn').textContent = t.noGit
  $('f-dest').textContent = info.docs_root
  // an existing project keeps the name it has: nothing to ask
  $('name-box').hidden = info.case === 'project'
  $('name').value = info.name || ''
  say('found', '')
  show('found')
  $('continue').focus()
}

async function adopt(e) {
  e.preventDefault()
  if (!found) return
  busy(true)
  say('found', t.preparing)
  try {
    const name = found.info.case === 'project' ? undefined : $('name').value.trim() || undefined
    const r = await hub.adopt(found.dir, name)
    if (r && r.error) say('found', r.error === 'taken' ? t.taken : t.folderBad, r.detail, true)
    else if (r && !r.ok) say('found', t.openFailed, r.error, true)
    else say('found', '')
  } finally { busy(false) }
}

// ---------- join the team's cam-docs ----------
function showJoin() {
  joinDir = null
  $('url').value = ''
  $('token').value = ''
  $('token-box').hidden = true
  $('join-go').textContent = t.joinGo
  say('join', '')
  show('joining')
  $('url').focus()
}

function askToken(host, again) {
  const h = host || t.server
  $('token-label').textContent = fill(t.tokenLabel, { host: h })
  $('token-box').hidden = false
  $('token').value = ''
  $('join-go').textContent = t.tokenGo
  say('join', fill(again ? t.authAgain : t.auth, { host: h }), '', again)     // the first ask is a request, not a failure
  $('token').focus()
}

async function join(e) {
  e.preventDefault()
  const url = $('url').value.trim()
  if (!url) return $('url').focus()
  const token = $('token-box').hidden ? undefined : $('token').value.trim()
  if (token === '') return $('token').focus()
  busy(true)
  say('join', t.joiningNow)
  try {
    const r = await hub.join(url, token, joinDir || undefined)
    if (!r || r.cancelled) return say('join', '')
    if (r.dir) joinDir = r.dir
    if (r.error === 'url') { say('join', ''); return $('url').focus() }
    // the CLI only tries a token for a host it can name (https URLs); without one, a token field would do nothing
    if (r.error === 'auth' && r.host) return askToken(r.host, !!token)
    if (r.error === 'auth') return say('join', t.authSsh, r.detail, true)
    if (r.error) {
      const host = r.host || t.server
      return say('join', fill(t[r.error] || t.failed, { host }), r.detail, true)
    }
    if (!r.ok) say('join', t.openFailed, r.error, true)
    else say('join', '')
  } finally { busy(false) }
}

async function main() {
  t = S[await hub.lang()] || S.es
  document.documentElement.lang = t === S.en ? 'en' : 'es'
  $('title').textContent = t.title
  $('lede').textContent = t.lede
  $('pick-title').textContent = t.pickTitle
  $('pick-help').textContent = t.pickHelp
  $('pick').textContent = t.pick
  $('join-title').textContent = t.joinTitle
  rich($('join-help'), t.joinHelp)
  $('join').textContent = t.join
  $('h-recent').textContent = t.recent
  $('join-back').textContent = $('found-back').textContent = t.back
  $('join-h').textContent = t.joinTitle
  rich($('join-lede'), t.joinHelp)
  $('url-label').textContent = t.urlLabel
  $('token-help').textContent = t.tokenHelp
  $('join-cancel').textContent = t.cancel
  $('found-h').textContent = t.foundTitle
  $('name-label').textContent = t.name
  $('change').textContent = t.change
  $('continue').textContent = t.continue

  $('pick').addEventListener('click', () => pickAndInspect('start'))
  $('change').addEventListener('click', () => pickAndInspect('found'))
  $('adopt-form').addEventListener('submit', adopt)
  $('join').addEventListener('click', showJoin)
  $('join-form').addEventListener('submit', join)
  // another URL may be another host: the token asked for the old one no longer applies
  $('url').addEventListener('input', () => {
    if ($('token-box').hidden) return
    $('token-box').hidden = true
    $('join-go').textContent = t.joinGo
    say('join', '')
  })
  for (const id of ['join-back', 'join-cancel', 'found-back']) $(id).addEventListener('click', () => { say('start', ''); show('start') })
  await load()
}

main()
