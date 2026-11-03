import type { Locale } from '@/i18n/config'
import { formatDate } from '@/lib/format'
import { safeHttpUrl } from '@/lib/url'

type Props = {
  name: string
  url: string | null
  fetchedAt: Date | string
  locale: Locale
  /** Localised "Source" / "來源" and "Fetched" / "抓取日期" labels. */
  labels: { source: string; fetched: string }
}

/** "來源：X · 抓取日期：YYYY-MM-DD" — shown on every data block. */
export default function SourceNote({ name, url, fetchedAt, locale, labels }: Props) {
  const sep = locale === 'zh' ? '：' : ': '
  return (
    <p className="text-xs text-subtle">
      {labels.source}
      {sep}
      {safeHttpUrl(url) ? (
        <a href={safeHttpUrl(url)!} target="_blank" rel="noopener noreferrer" className="underline">
          {name}
        </a>
      ) : (
        name
      )}
      {' · '}
      {labels.fetched}
      {sep}
      <time dateTime={new Date(fetchedAt).toISOString()}>{formatDate(fetchedAt, locale)}</time>
    </p>
  )
}
