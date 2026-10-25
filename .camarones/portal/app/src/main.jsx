import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import Shell from './shell/Shell.jsx'
import './portal.css'
import './styles.css'

// The shell owns the page: header, sidebar, router; the views read the portal's state from core.js.
createRoot(document.getElementById('app')).render(<StrictMode><Shell /></StrictMode>)
