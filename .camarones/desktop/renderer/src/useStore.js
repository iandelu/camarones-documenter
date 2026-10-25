import { useSyncExternalStore } from 'react'

// A store with get() and subscribe(fn) (jobs.js) as React state.
export const useStore = (store) => useSyncExternalStore(store.subscribe, store.get)
