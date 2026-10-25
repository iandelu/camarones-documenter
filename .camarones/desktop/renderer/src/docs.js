// The portal (the reader) from the app: it is served by the same project server, one folder up from /desktop/, and
// a project window opens it in the system browser. Pure.

// An address of the portal: origin is this window's (location.origin), hash the portal's route ('#/', '#/review'…).
export const portalUrl = (origin, hash = '#/') => `${String(origin).replace(/\/+$/, '')}/${hash || '#/'}`
