import type { Metadata } from 'next'
import Link from 'next/link'
import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import { hasLocale, type Locale } from '@/i18n/config'
import { getDictionary, type Dictionary } from '@/i18n/dictionaries'
import { parseCompareIds } from '@/lib/compare-params'
import { getCompareItemsCached } from '@/lib/data'
import { formatMoney, formatPercent, formatRange, listSep } from '@/lib/format'
import { displayName } from '@/lib/names'
import type { CompareItem } from '@/lib/queries/compare'
import NoData from '@/components/NoData'
import SourceNote from '@/components/SourceNote'

export async function generateMetadata({ params }: PageProps<'/[locale]/compare'>): Promise<Metadata> {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  return { title: (await getDictionary(locale)).compare.title }
}

export default async function ComparePage({ params, searchParams }: PageProps<'/[locale]/compare'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  return (
    <div className="min-w-0 space-y-6">
      <h1 className="text-2xl font-bold">{dict.compare.title}</h1>
      <Suspense fallback={<p className="text-subtle">{dict.compare.loading}</p>}>
        <Results locale={locale} dict={dict} searchParams={searchParams} />
      </Suspense>
    </div>
  )
}

async function Results({
  locale,
  dict,
  searchParams,
}: {
  locale: Locale
  dict: Dictionary
  searchParams: PageProps<'/[locale]/compare'>['searchParams']
}) {
  const ids = parseCompareIds((await searchParams).ids)
  const items = ids.length ? await getCompareItemsCached(ids.join(',')) : []
  if (items.length < 2) {
    return (
      <div className="space-y-3">
        <p>{dict.compare.needTwo}</p>
        <Link href={`/${locale}/explore`} prefetch={false} className="text-brand underline">
          {dict.compare.backToExplore}
        </Link>
      </div>
    )
  }
  return <CompareTable items={items} locale={locale} dict={dict} />
}

function Dash() {
  return <span className="text-subtle">—</span>
}

function CompareTable({ items, locale, dict }: { items: CompareItem[]; locale: Locale; dict: Dictionary }) {
  const t = dict.compare
  const labels = { source: dict.common.source, fetched: dict.common.fetchedAt }
  const rowHead = 'sticky left-0 z-10 w-28 min-w-28 border-b border-line bg-page px-3 py-2 text-left align-top font-medium'
  const cell = 'min-w-48 border-b border-line px-3 py-2 align-top break-words'

  const rows: { label: string; render: (i: CompareItem) => React.ReactNode }[] = [
    {
      label: t.school,
      render: (i) => (
        <Link href={`/${locale}/schools/${i.institution.id}`} prefetch={false} className="text-brand hover:underline">
          {displayName(locale, i.institution.nameZh, i.institution.nameEn)}
        </Link>
      ),
    },
    { label: t.country, render: (i) => (i.institution.country === 'TW' ? t.tw : t.us) },
    { label: t.control, render: (i) => (i.institution.control ? dict.explore[i.institution.control] : <Dash />) },
    { label: t.field, render: (i) => (i.field ? displayName(locale, i.field.nameZh, i.field.nameEn) : <Dash />) },
    {
      label: t.requirement,
      render: (i) => {
        const r = i.requirementSummary
        if (!r) return <Dash />
        if (r.kind === 'tw_apply') {
          if (r.sieve.length === 0) return <Dash />
          return (
            <>
              <p className="text-xs text-subtle">{dict.program.applyYear.replace('{year}', String(r.year))}</p>
              <ul className="space-y-1">
                {r.sieve.map((s) => (
                  <li key={s.order}>
                    {t.sieveStep
                      .replace('{order}', String(s.order))
                      .replace('{label}', s.label)
                      .replace('{score}', String(s.min_score))}
                  </li>
                ))}
              </ul>
            </>
          )
        }
        return (
          <>
            <p className="text-xs text-subtle">{r.year}</p>
            <p>
              {t.satTotal}: {formatRange(r.satTotal)}
            </p>
            <p>
              {t.act}: {formatRange(r.act)}
            </p>
          </>
        )
      },
    },
    {
      label: t.admission,
      render: (i) => {
        const a = i.admission
        if (!a || a.series.length === 0) return <Dash />
        return (
          <ul className="space-y-1">
            {a.kind === 'tw_distribution'
              ? a.series.map((s) => (
                  <li key={s.year}>
                    {t.minScoreYear.replace('{year}', String(s.year)).replace('{score}', s.minScore === null ? '—' : String(s.minScore))}
                  </li>
                ))
              : a.series.map((s) => (
                  <li key={s.year}>
                    {t.rateYear.replace('{year}', String(s.year)).replace('{rate}', formatPercent(s.rate, locale))}
                  </li>
                ))}
          </ul>
        )
      },
    },
    {
      label: t.tuition,
      render: (i) => {
        const c = i.tuition
        if (!c || (c.local === null && c.outOfState === null)) return <Dash />
        return (
          <>
            <p className="text-xs text-subtle">{t.tuitionYear.trim().replace('{year}', String(c.year))}</p>
            <p>
              {t.local}: {formatMoney(c.local, c.currency, locale)}
            </p>
            <p>
              {t.outOfState}: {formatMoney(c.outOfState, c.currency, locale)}
            </p>
          </>
        )
      },
    },
    {
      label: t.strengths,
      render: (i) => (i.topStrengthFields.length ? i.topStrengthFields.join(listSep(locale)) : <Dash />),
    },
    {
      label: t.sources,
      render: (i) =>
        i.sources.length ? (
          <div className="space-y-1">
            {i.sources.map((s) => (
              <SourceNote key={`${s.name}\n${s.url}`} name={s.name} url={s.url} fetchedAt={s.fetchedAt} locale={locale} labels={labels} />
            ))}
          </div>
        ) : (
          <NoData label={dict.common.noData} />
        ),
    },
  ]

  return (
    <div className="max-w-full overflow-x-auto rounded border border-line">
      <table className="w-max min-w-full border-separate border-spacing-0 text-sm">
        <thead>
          <tr>
            <th className={`${rowHead} bg-page`} scope="col">
              <span className="sr-only">{t.title}</span>
            </th>
            {items.map((i) => (
              <th key={i.programId} scope="col" className={`${cell} text-left font-semibold`}>
                <Link href={`/${locale}/programs/${i.programId}`} prefetch={false} className="text-brand hover:underline">
                  {displayName(locale, i.programNameZh, i.programNameEn)}
                </Link>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.label}>
              <th scope="row" className={rowHead}>
                {r.label}
              </th>
              {items.map((i) => (
                <td key={i.programId} className={cell}>
                  {r.render(i)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
