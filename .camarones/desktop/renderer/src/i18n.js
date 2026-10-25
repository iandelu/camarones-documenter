// The app's strings, es and en (AGENTS.md §3: the intern shrimp, at most one joke per screen, none in errors).
export const S = {
  es: {
    'nav.summary': 'Resumen', 'nav.plan': 'Plan', 'nav.interviews': 'Entrevistas', 'nav.team': 'Equipo',
    'nav.quality': 'Calidad', 'nav.docs': 'Docs', 'nav.machine': 'Máquina', 'nav.kitdev': 'Kit dev',
    'nav.project': 'Secciones del proyecto', 'nav.app': 'Esta app', rail: 'Proyectos', 'rail.add': 'Añadir un proyecto',
    'rail.missing': 'no está en el disco',
    jobs: 'Trabajos', 'jobs.none': 'Nada en curso', fold: 'Plegar', unfold: 'Desplegar',
    'soon.title': 'Esta sección se está rehaciendo aquí', 'soon.body': 'Mientras tanto, la tienes en el Taller.',
    'soon.open': 'Abrir en el Taller',
    'hub.title': 'Elige un proyecto',
    'hub.new': 'Crear proyecto', 'hub.join': 'Unirse al del equipo', 'hub.add': 'Añadir carpeta', 'hub.open': 'Abrir',
    'hub.empty': 'Aún no hay proyectos en esta máquina', 'hub.emptyBody': 'Crea uno, únete al del equipo o añade una carpeta que ya tenga cam-docs.',
    'hub.failed': 'No he podido leer los proyectos', 'hub.opening': 'Abriendo {name}…', 'hub.error': 'No ha salido bien',
    'hub.name': 'Nombre del proyecto', 'hub.from': 'Repo cam-docs del equipo (opcional)', 'hub.url': 'URL del repo cam-docs del equipo',
    'hub.create': 'Crear y elegir carpeta', 'hub.joinGo': 'Unirse y elegir carpeta', cancel: 'Cancelar',
    'outside.title': 'Esto es la app de escritorio', 'outside.body': 'Ábrela con camaron app. En el navegador tienes el portal.',
    'outside.portal': 'Ir al portal',
  },
  en: {
    'nav.summary': 'Summary', 'nav.plan': 'Plan', 'nav.interviews': 'Interviews', 'nav.team': 'Team',
    'nav.quality': 'Quality', 'nav.docs': 'Docs', 'nav.machine': 'Machine', 'nav.kitdev': 'Kit dev',
    'nav.project': 'Project sections', 'nav.app': 'This app', rail: 'Projects', 'rail.add': 'Add a project',
    'rail.missing': 'not on disk',
    jobs: 'Jobs', 'jobs.none': 'Nothing running', fold: 'Fold', unfold: 'Unfold',
    'soon.title': 'This section is being rebuilt here', 'soon.body': 'In the meantime, it is in the Workshop.',
    'soon.open': 'Open in the Workshop',
    'hub.title': 'Pick a project',
    'hub.new': 'Create project', 'hub.join': 'Join the team\'s', 'hub.add': 'Add folder', 'hub.open': 'Open',
    'hub.empty': 'No projects on this machine yet', 'hub.emptyBody': 'Create one, join the team\'s or add a folder that already has cam-docs.',
    'hub.failed': 'I could not read the projects', 'hub.opening': 'Opening {name}…', 'hub.error': 'That did not work',
    'hub.name': 'Project name', 'hub.from': 'The team\'s cam-docs repo (optional)', 'hub.url': 'URL of the team\'s cam-docs repo',
    'hub.create': 'Create and pick a folder', 'hub.joinGo': 'Join and pick a folder', cancel: 'Cancel',
    'outside.title': 'This is the desktop app', 'outside.body': 'Open it with camaron app. In the browser you have the portal.',
    'outside.portal': 'Go to the portal',
  },
}

let current = 'es'
export const setLang = (l) => { current = S[l] ? l : 'es'; if (typeof document !== 'undefined') document.documentElement.lang = current }
export const lang = () => current
export const t = (k, vars = {}) => (S[current][k] ?? S.es[k] ?? k).replace(/\{(\w+)\}/g, (m, v) => (v in vars ? String(vars[v]) : m))
