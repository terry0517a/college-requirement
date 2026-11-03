'use client'

import { useRouter } from 'next/navigation'
import type { Locale } from '@/i18n/config'

type Region = 'all' | 'tw' | 'us'

export default function RegionSelect({
  locale,
  labels,
}: {
  locale: Locale
  labels: { label: string; all: string; tw: string; us: string }
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
        defaultValue="all"
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
