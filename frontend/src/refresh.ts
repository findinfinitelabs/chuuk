/**
 * refresh.ts
 * Purpose: let pages with unsaved work register a save function, so that
 * when a new version is deployed and the person accepts the refresh, their
 * work is saved first and the page reloads to the same place.
 */

type SaveHandler = () => Promise<void> | void

const handlers = new Set<SaveHandler>()

/** Register a function that saves the page's unsaved work; returns the unregister. */
export function registerSaveHandler(fn: SaveHandler): () => void {
  handlers.add(fn)
  return () => { handlers.delete(fn) }
}

/** Run every registered save; failures are swallowed so the reload still happens. */
export async function saveAll(): Promise<void> {
  await Promise.all(Array.from(handlers).map(async (fn) => { try { await fn() } catch { /* best effort */ } }))
}

/** Save everything, then reload the page at its current URL (same route, same query). */
export async function saveAndReload(): Promise<void> {
  await saveAll()
  window.location.reload()
}
