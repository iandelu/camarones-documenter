import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Shell from './shell/Shell.jsx'
import { captureToken } from './token.js'
import './portal.css'
import './styles.css'

// First: the machine token out of the address, before the router reads it.
captureToken()

// The shell owns the page: header, sidebar, router; the views read the portal's state from core.js.
createRoot(document.getElementById('app')).render(<StrictMode><Shell /></StrictMode>)
