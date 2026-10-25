// Strings of the shared components, in es and en. Each app keeps its own screens' strings; phase 1 of the redesign
// moves the portal's here (one dictionary per app, one language rule for both).
export const S = {
  en: {
    crumbs: 'Breadcrumb',
    loading: 'Loading…',
    close: 'Close',
  },
  es: {
    crumbs: 'Ruta',
    loading: 'Cargando…',
    close: 'Cerrar',
  },
}

// The reader's choice (cam-lang), else <html lang> (the portal sets it from the browser, the desktop app from
// ~/.camarones.json), else English, the canonical docs.
export function lang() {
  let l = ''
  try { l = localStorage.getItem('cam-lang') || '' } catch { /* private mode, or no browser */ }
  if (!S[l]) l = typeof document === 'undefined' ? '' : document.documentElement.lang.slice(0, 2)
  return S[l] ? l : 'en'
}

export function t(key, l = lang()) {
  return S[l]?.[key] ?? S.en[key] ?? key
}
