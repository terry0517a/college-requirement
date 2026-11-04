'use client'

import { useSyncExternalStore } from 'react'
import { FAVORITES_KEY, readList, subscribeLists, toggleInList } from '@/lib/local-lists'

/** Star toggle; the server render and first client render are "not favorited", localStorage is read after hydration. */
export default function FavoriteButton({
  institutionId,
  labels,
}: {
  institutionId: number
  labels: { add: string; remove: string }
}) {
  const fav = useSyncExternalStore(
    subscribeLists,
    () => readList(FAVORITES_KEY).includes(institutionId),
    () => false,
  )
  return (
    <button
      type="button"
      onClick={() => toggleInList(FAVORITES_KEY, institutionId)}
      aria-pressed={fav}
      className="rounded border border-line px-3 py-1 text-sm hover:border-brand"
    >
      <span aria-hidden="true">{fav ? '★' : '☆'}</span> {fav ? labels.remove : labels.add}
    </button>
  )
}
