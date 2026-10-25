import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Native from './Native.jsx'
import * as directives from './content/directives.js'
import * as tables from './content/tables.js'
import * as generated from './content/generated.js'
import * as zones from './zones.js'
import { captureToken } from './token.js'
import './styles.css'

// First: the machine token out of the address, before the router reads it.
captureToken()

// Helpers the docs renderer (legacy/doc.js) uses: directives and live tables.
window.CamaronContent = { directives, tables, generated }
// Navigation (zones, breadcrumbs, ⌘K entries, Home KPIs) for the router in legacy/app.js.
window.CamaronZones = zones

const host = document.getElementById('native')
const root = createRoot(host)
window.CamaronNative = {
  show(view, arg) {
    host.hidden = false
    root.render(<StrictMode><Native view={view} arg={arg || null} /></StrictMode>)
  },
  hide() {
    if (host.hidden) return
    host.hidden = true
    root.render(null)
  },
}
window.dispatchEvent(new Event('camaron:native-ready'))
