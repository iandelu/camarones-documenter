import { cpSync, existsSync, readFileSync } from 'node:fs'
import { extname, join, normalize, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// The shared kit (theme, components, strings) the portal and the desktop app both use; it has no build of its own.
const ui = fileURLToPath(new URL('../../ui', import.meta.url))
const theme = join(ui, 'theme')
const types = { '.css': 'text/css', '.woff2': 'font/woff2', '.txt': 'text/plain; charset=utf-8' }

// The theme keeps its published address, theme/…: served from ui/theme in dev, copied into the build.
function camaronTheme() {
  let outDir
  return {
    name: 'camaron-theme',
    configResolved(config) { outDir = config.build.outDir },
    configureServer(server) {
      server.middlewares.use('/theme', (req, res, next) => {
        const file = normalize(join(theme, decodeURIComponent(req.url.split('?')[0])))
        if (!file.startsWith(theme + sep) || !existsSync(file) || !types[extname(file)]) return next()
        res.setHeader('Content-Type', types[extname(file)])
        res.end(readFileSync(file))
      })
    },
    closeBundle() {
      cpSync(theme, join(outDir, 'theme'), { recursive: true, filter: (src) => !src.endsWith('.test.js') })
    },
  }
}

// The portal (served by `camaron up` at /, exported by `camaron portal`); the build is committed so users never need
// Node for it. Relative base: the static export also works under a sub-path (GitLab/GitHub Pages).
// Output goes to app-build/, not dist/: the kit installer skips dist folders.
export default defineConfig({
  base: './',
  plugins: [react(), camaronTheme()],
  resolve: { alias: { '@camaron/ui': join(ui, 'src') }, dedupe: ['react', 'react-dom'] },
  build: { outDir: '../app-build', emptyOutDir: true, manifest: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:8080' }, fs: { allow: ['.', ui] } },
  test: { environment: 'node', include: ['src/**/*.test.{js,jsx}', '../../ui/**/*.test.{js,jsx}'] },
})
