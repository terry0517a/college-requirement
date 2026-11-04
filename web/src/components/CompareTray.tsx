'use client'

import Link from 'next/link'
import { useSyncExternalStore } from 'react'
import { COMPARE_KEY, snapshotList, subscribeLists, writeList } from '@/lib/local-lists'

/** Fixed bottom bar with the compare count; renders nothing until localStorage says there is a selection. */
export default function CompareTray({
  locale,
  labels,
}: {
  locale: string
  labels: { tray: string; start: string; clear: string }
}) {
  const snap = useSyncExternalStore(subscribeLists, () => snapshotList(COMPARE_KEY), () => '')
  if (!snap) return null
  const n = snap.split(',').length
  return (
    <>
      {/* in-flow spacer so the fixed bar never covers the footer / page end */}
      <div aria-hidden="true" className="h-16" />
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-page">
        <div className="mx-auto flex max-w-5xl items-center gap-3 px-4 py-3 text-sm">
          <span>{labels.tray.replace('{n}', String(n))}</span>
          <Link
            href={`/${locale}/compare?ids=${snap}`}
            prefetch={false}
            className="rounded bg-brand px-3 py-1 text-white"
          >
            {labels.start}
          </Link>
          <button type="button" onClick={() => writeList(COMPARE_KEY, [])} className="ml-auto text-subtle underline">
            {labels.clear}
          </button>
        </div>
      </div>
    </>
  )
}
