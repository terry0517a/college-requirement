'use client'

import { useSyncExternalStore } from 'react'

const KEY = 'favorites:v1'
const EVENT = 'favorites:change'

function read(): number[] {
  try {
    const v = JSON.parse(window.localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(v) ? v.filter((x): x is number => Number.isInteger(x)) : []
  } catch {
    return []
  }
}

function subscribe(cb: () => void) {
  window.addEventListener('storage', cb)
  window.addEventListener(EVENT, cb)
  return () => {
    window.removeEventListener('storage', cb)
    window.removeEventListener(EVENT, cb)
  }
}

/** Star toggle; the server render and first client render are "not favorited", localStorage is read after hydration. */
export default function FavoriteButton({
  institutionId,
  labels,
}: {
  institutionId: number
  labels: { add: string; remove: string }
}) {
  const fav = useSyncExternalStore(
    subscribe,
    () => read().includes(institutionId),
    () => false,
  )
  function toggle() {
    try {
      const cur = read()
      const next = cur.includes(institutionId) ? cur.filter((x) => x !== institutionId) : [...cur, institutionId]
      window.localStorage.setItem(KEY, JSON.stringify(next))
    } catch {
      // storage unavailable: the button stays inert
    }
    window.dispatchEvent(new Event(EVENT))
  }
  return (
    <button
      type="button"
      onClick={toggle}
      aria-pressed={fav}
      className="rounded border border-line px-3 py-1 text-sm hover:border-brand"
    >
      <span aria-hidden="true">{fav ? '★' : '☆'}</span> {fav ? labels.remove : labels.add}
    </button>
  )
}
