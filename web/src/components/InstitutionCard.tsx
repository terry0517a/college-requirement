import Link from 'next/link'
import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import { formatDate, formatMoney } from '@/lib/format'
import { displayName } from '@/lib/names'
import type { ExploreItem } from '@/lib/queries/explore'
import SourceNote from './SourceNote'

export default function InstitutionCard({
  item,
  locale,
  dict,
}: {
  item: ExploreItem
  locale: Locale
  dict: Dictionary
}) {
  const main = displayName(locale, item.nameZh, item.nameEn)
  const otherRaw = locale === 'zh' ? item.nameEn : item.nameZh
  const other = otherRaw && otherRaw !== main ? otherRaw : null
  const t = dict.explore
  const tu = item.tuition
  const tuitionValue = tu ? (tu.outOfState ?? tu.local) : null
  const tuition =
    item.country === 'US'
      ? tuitionValue !== null && tu
        ? formatMoney(tuitionValue, tu.currency, locale)
        : dict.common.noData
      : '—'
  const labels = { source: dict.common.source, fetched: dict.common.fetchedAt }
  const showTuitionSource =
    item.country === 'US' &&
    tu &&
    tuitionValue !== null &&
    (tu.source.name !== item.source.name || formatDate(tu.fetchedAt, locale) !== formatDate(item.fetchedAt, locale))
  const place = item.country === 'US' ? [item.city, item.region].filter(Boolean).join(', ') : ''
  return (
    <li className="rounded border border-line p-4">
      <h2 className="text-lg font-semibold break-words">
        <Link href={`/${locale}/schools/${item.id}`} prefetch={false} className="hover:text-brand">
          {main}
        </Link>
      </h2>
      {other && <p className="text-sm text-subtle break-words">{other}</p>}
      <p className="mt-1 text-sm text-subtle">
        {[
          item.country === 'TW' ? t.countryTW : t.countryUS,
          place || null,
          item.control ? t[item.control] : null,
        ]
          .filter(Boolean)
          .join(' · ')}
      </p>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        <dt className="text-subtle">{t.tuition}</dt>
        <dd>
          {tuition}
          {item.country === 'US' && tu && tuitionValue !== null && (
            <span className="block text-xs text-subtle">
              {t.tuitionUsEstimate.replace('{year}', String(tu.year))}
            </span>
          )}
          {showTuitionSource && tu && (
            <SourceNote
              name={tu.source.name}
              url={tu.source.url}
              fetchedAt={tu.fetchedAt}
              locale={locale}
              labels={labels}
            />
          )}
        </dd>
        {item.studentSize !== null && (
          <>
            <dt className="text-subtle">{t.students}</dt>
            <dd>{item.studentSize.toLocaleString(locale === 'zh' ? 'zh-TW' : 'en-US')}</dd>
          </>
        )}
      </dl>
      {item.matchedPrograms.length > 0 && (
        <div className="mt-2 text-sm">
          <span className="text-subtle">{t.matchedPrograms}{locale === 'zh' ? '：' : ': '}</span>
          {item.matchedPrograms.map((p) => displayName(locale, p.nameZh, p.nameEn)).join('、')}
        </div>
      )}
      <div className="mt-3">
        <SourceNote
          name={item.source.name}
          url={item.source.url}
          fetchedAt={item.fetchedAt}
          locale={locale}
          labels={labels}
        />
      </div>
    </li>
  )
}
