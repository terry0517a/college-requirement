'use client'

import { Suspense } from 'react'
import { useRouter, useSearchParams } from 'next/navigation'
import type { Locale } from '@/i18n/config'

type Region = 'all' | 'tw' | 'us'

type Labels = { label: string; all: string; tw: string; us: string }

/** Static shell renders "all"; the Suspense child reflects ?region= after hydration. */
export default function RegionSelect({ locale, labels }: { locale: Locale; labels: Labels }) {
  return (
    <Suspense fallback={<Select locale={locale} labels={labels} current="all" />}>
      <WithParams locale={locale} labels={labels} />
    </Suspense>
  )
}

function WithParams({ locale, labels }: { locale: Locale; labels: Labels }) {
  const r = useSearchParams().get('region')
  return <Select locale={locale} labels={labels} current={r === 'tw' || r === 'us' ? r : 'all'} />
}

function Select({
  locale,
  labels,
  current,
}: {
  locale: Locale
  labels: Labels
  current: Region
}) {
  const router = useRouter()
  function onChange(region: Region) {
    document.cookie = `region=${region}; path=/; max-age=31536000; samesite=lax`
    router.push(`/${locale}/explore?region=${region}`)
  }
  return (
    <label className="flex items-center gap-1 text-sm">
      <span className="text-subtle">{labels.label}</span>
      <select
        value={current}
        onChange={(e) => onChange(e.target.value as Region)}
        className="rounded border border-line bg-page px-2 py-1"
      >
        <option value="all">{labels.all}</option>
        <option value="tw">{labels.tw}</option>
        <option value="us">{labels.us}</option>
      </select>
    </label>
  )
}
