import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Served by the kit's portal server at /next; the build is committed so users never need Node for it.
// Output goes to app-build/, not dist/: the kit installer skips dist folders.
export default defineConfig({
  base: '/next/',
  plugins: [react()],
  build: { outDir: '../app-build', emptyOutDir: true, manifest: true, sourcemap: false },
  server: { proxy: { '/api': 'http://127.0.0.1:8080' } },
  test: { environment: 'node' },
})
