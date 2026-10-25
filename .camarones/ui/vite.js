// What both apps' Vite configs share: the kit's folder, its alias, and the theme published at theme/ (served from
// ui/theme in dev, copied into the build), so every address that links theme/tokens.css or its fonts keeps working.
import { cpSync, existsSync, readFileSync } from 'node:fs'
import { extname, join, normalize, sep } from 'node:path'
import { fileURLToPath } from 'node:url'

export const UI = fileURLToPath(new URL('.', import.meta.url)).replace(/[\\/]$/, '')
const THEME = join(UI, 'theme')
const TYPES = { '.css': 'text/css', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8' }

// resolve: the @camaron/ui alias, with React deduped so the kit's components use the app's own copy.
export const uiResolve = { alias: { '@camaron/ui': join(UI, 'src') }, dedupe: ['react', 'react-dom'] }

export function camaronTheme() {
  let outDir
  return {
    name: 'camaron-theme',
    configResolved(config) { outDir = config.build.outDir },
    configureServer(server) {
      server.middlewares.use('/theme', (req, res, next) => {
        const file = normalize(join(THEME, decodeURIComponent(req.url.split('?')[0])))
        if (!file.startsWith(THEME + sep) || !existsSync(file) || !TYPES[extname(file)]) return next()
        res.setHeader('Content-Type', TYPES[extname(file)])
        res.end(readFileSync(file))
      })
    },
    closeBundle() {
      cpSync(THEME, join(outDir, 'theme'), { recursive: true, filter: (src) => !src.endsWith('.test.js') })
    },
  }
}
