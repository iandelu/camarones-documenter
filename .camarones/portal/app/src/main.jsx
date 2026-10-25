import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Shell from './shell/Shell.jsx'
import * as directives from './content/directives.js'
import * as tables from './content/tables.js'
import * as zones from './zones.js'
import './styles.css'

// Helpers the docs renderer (legacy/doc.js) uses: directives and live tables.
window.CamaronContent = { directives, tables }
// Navigation (zones, breadcrumbs, ⌘K entries, Home KPIs), also read by the plain scripts in legacy/app.js.
window.CamaronZones = zones

// The shell owns the page: header, sidebar, router. The plain scripts (deferred, so they ran before this module)
// expose their views as window.CamaronLegacy.
createRoot(document.getElementById('app')).render(<StrictMode><Shell /></StrictMode>)
