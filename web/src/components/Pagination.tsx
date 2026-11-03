import Link from 'next/link'
import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import { PAGE_SIZE, toQueryString, type ExploreParams } from '@/lib/explore-params'

export default function Pagination({
  params,
  total,
  locale,
  dict,
}: {
  params: ExploreParams
  total: number
  locale: Locale
  dict: Dictionary
}) {
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const pastEnd = total > 0 && params.page > pages
  if (pages <= 1 && !pastEnd) return null
  const href = (page: number) => {
    const qs = toQueryString(params, { page })
    return `/${locale}/explore${qs ? `?${qs}` : ''}`
  }
  const t = dict.explore
  const cls = 'rounded border border-line px-3 py-1 hover:border-brand'
  return (
    <nav aria-label={t.pagination} className="flex flex-wrap items-center justify-between gap-2 text-sm">
      {pastEnd ? (
        <Link href={href(pages)} prefetch={false} className={cls}>
          {t.page.replace('{page}', String(pages)).replace('{pages}', String(pages))}
        </Link>
      ) : params.page > 1 ? (
        <Link href={href(params.page - 1)} prefetch={false} className={cls} rel="prev">
          {t.prev}
        </Link>
      ) : (
        <span />
      )}
      <span className="text-subtle">
        {t.page.replace('{page}', String(params.page)).replace('{pages}', String(pages))}
      </span>
      {params.page < pages ? (
        <Link href={href(params.page + 1)} prefetch={false} className={cls} rel="next">
          {t.next}
        </Link>
      ) : (
        <span />
      )}
    </nav>
  )
}
