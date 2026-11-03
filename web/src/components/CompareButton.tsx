'use client'

import { useSyncExternalStore } from 'react'
import { MAX_COMPARE } from '@/lib/compare-params'
import { COMPARE_KEY, snapshotList, subscribeLists, toggleInList } from '@/lib/local-lists'

/** Add / remove a program in the compare list; server render and first client render show "add". */
export default function CompareButton({
  programId,
  labels,
}: {
  programId: number
  labels: { add: string; remove: string; full: string }
}) {
  const snap = useSyncExternalStore(subscribeLists, () => snapshotList(COMPARE_KEY), () => '')
  const ids = snap ? snap.split(',').map(Number) : []
  const inList = ids.includes(programId)
  const full = !inList && ids.length >= MAX_COMPARE
  return (
    <button
      type="button"
      onClick={() => toggleInList(COMPARE_KEY, programId, MAX_COMPARE)}
      aria-pressed={inList}
      aria-disabled={full}
      className={`rounded border border-line px-3 py-1 text-sm ${full ? 'text-subtle' : 'hover:border-brand'}`}
    >
      {inList ? labels.remove : full ? labels.full : labels.add}
    </button>
  )
}
