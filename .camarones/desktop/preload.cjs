'use strict'
// The only bridge between a window and the main process (sandboxed: only `electron` can be required here).
// A project window gets window.camaronApp with its server's token, and only while it shows that server; the hub
// window gets window.camaronHub. Nothing else of Node or Electron reaches the page.
const { contextBridge, ipcRenderer } = require('electron')

const arg = (k) => (process.argv.find((a) => a.startsWith(`--camaron-${k}=`)) || '').slice(`--camaron-${k}=`.length)
const token = arg('token')
const origin = arg('origin')

if (process.argv.includes('--camaron-hub')) {
  contextBridge.exposeInMainWorld('camaronHub', {
    list: () => ipcRenderer.invoke('hub:list'),
    open: (root) => ipcRenderer.invoke('hub:open', root),
    add: () => ipcRenderer.invoke('hub:add'),
    create: (name, from) => ipcRenderer.invoke('hub:new', { name, from }),
    join: (url) => ipcRenderer.invoke('hub:join', { url }),
    lang: () => ipcRenderer.invoke('hub:lang'),
  })
} else if (token && origin && location.origin === origin) {
  contextBridge.exposeInMainWorld('camaronApp', {
    token,
    hub: () => ipcRenderer.invoke('app:hub'),
    openExternal: (url) => ipcRenderer.invoke('app:external', url),
    reveal: (file) => ipcRenderer.invoke('app:reveal', file),
    pickFiles: (kind) => ipcRenderer.invoke('app:pick', kind),
    relaunch: () => ipcRenderer.invoke('app:relaunch'),
    theme: (theme) => ipcRenderer.invoke('app:theme', theme),
    menu: (x, y) => ipcRenderer.invoke('app:menu', { x, y }),
  })
}
