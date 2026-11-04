/**
 * glossSettings.ts
 * Purpose: the reader's choice of how much dictionary help to show in glossed
 * text. "Show dictionary indicators" adds a faint dotted underline to every
 * word the dictionary holds; off, the text stays clean and only phrases are
 * underlined. Stored per browser; shared by every page through a tiny store.
 */

import { useSyncExternalStore } from 'react'

const KEY = 'dictionary-indicators'
let value = false
try { value = localStorage.getItem(KEY) === 'on' } catch { /* private window or blocked storage */ }
const listeners = new Set<() => void>()

export function setIndicators(on: boolean) {
  value = on
  try { localStorage.setItem(KEY, on ? 'on' : 'off') } catch { /* ignore */ }
  listeners.forEach((l) => l())
}

export function useIndicators(): boolean {
  return useSyncExternalStore((l) => { listeners.add(l); return () => { listeners.delete(l) } }, () => value, () => value)
}
