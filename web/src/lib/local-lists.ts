// Client-only helpers for id lists kept in localStorage (favorites, compare).
// Never import db / queries here.

export const COMPARE_KEY = 'compare:v1'
export const FAVORITES_KEY = 'favorites:v1'
export const LISTS_EVENT = 'local-lists'

export function readList(key: string): number[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(key) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is number => Number.isInteger(x)) : []
  } catch {
    return []
  }
}

export function writeList(key: string, ids: number[]): void {
  try {
    window.localStorage.setItem(key, JSON.stringify(ids))
  } catch {
    // storage unavailable: nothing is persisted
  }
  window.dispatchEvent(new Event(LISTS_EVENT))
}

export function toggleInList(key: string, id: number, max?: number): { ids: number[]; added: boolean; full: boolean } {
  const cur = readList(key)
  if (cur.includes(id)) {
    const ids = cur.filter((x) => x !== id)
    writeList(key, ids)
    return { ids, added: false, full: false }
  }
  if (max !== undefined && cur.length >= max) return { ids: cur, added: false, full: true }
  const ids = [...cur, id]
  writeList(key, ids)
  return { ids, added: true, full: false }
}

export function subscribeLists(cb: () => void): () => void {
  window.addEventListener('storage', cb)
  window.addEventListener(LISTS_EVENT, cb)
  return () => {
    window.removeEventListener('storage', cb)
    window.removeEventListener(LISTS_EVENT, cb)
  }
}

/** Stable string snapshot (comma-joined ids) for useSyncExternalStore. */
export function snapshotList(key: string): string {
  return readList(key).join(',')
}
