import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { hasLocale, locales, type Locale } from '@/i18n/config'
import { getDictionary, type Dictionary } from '@/i18n/dictionaries'
import { getSchoolCached, listSchoolIdsForPrerender } from '@/lib/data'
import { formatMoney, formatPercent, formatRange } from '@/lib/format'
import { displayName } from '@/lib/names'
import { parseId, type SchoolDetail } from '@/lib/queries/school'
import FavoriteButton from '@/components/FavoriteButton'
import NoData from '@/components/NoData'
import SchoolToc from '@/components/SchoolToc'
import SourceNote from '@/components/SourceNote'
import StrengthList from '@/components/StrengthList'

export async function generateStaticParams() {
  const ids = await listSchoolIdsForPrerender(20)
  return locales.flatMap((locale) => ids.map((id) => ({ locale, id: String(id) })))
}

export async function generateMetadata({ params }: PageProps<'/[locale]/schools/[id]'>): Promise<Metadata> {
  const { locale, id: raw } = await params
  if (!hasLocale(locale)) notFound()
  const id = parseId(raw)
  if (id === null) notFound()
  const school = await getSchoolCached(id)
  if (!school) notFound()
  const dict = await getDictionary(locale)
  const i = school.institution
  return {
    title: `${displayName(locale, i.nameZh, i.nameEn)} | ${dict.site.name}`,
    alternates: { languages: { 'zh-Hant-TW': `/zh/schools/${id}`, en: `/en/schools/${id}` } },
  }
}

// notFound() runs here, before any <Suspense>, so bad ids get a real 404.
export default async function SchoolPage({ params }: PageProps<'/[locale]/schools/[id]'>) {
  const { locale, id: raw } = await params
  if (!hasLocale(locale)) notFound()
  const id = parseId(raw)
  if (id === null) notFound()
  const school = await getSchoolCached(id)
  if (!school) notFound()
  const dict = await getDictionary(locale)
  return <SchoolView school={school} locale={locale} dict={dict} />
}

function SchoolView({ school, locale, dict }: { school: SchoolDetail; locale: Locale; dict: Dictionary }) {
  const t = dict.school
  const i = school.institution
  const labels = { source: dict.common.source, fetched: dict.common.fetchedAt }
  const name = displayName(locale, i.nameZh, i.nameEn)
  const otherRaw = locale === 'zh' ? i.nameEn : i.nameZh
  const other = otherRaw && otherRaw !== name ? otherRaw : null
  const place = [i.city, i.region].filter(Boolean).join(', ')
  const toc = [
    { id: 'summary', label: t.summary },
    { id: 'admissions', label: t.admissions },
    { id: 'strengths', label: t.strengths },
    { id: 'costs', label: t.costs },
    { id: 'sources', label: t.sources },
  ]
  const fieldName = (f: { nameZh: string; nameEn: string }) => (locale === 'zh' ? f.nameZh : f.nameEn)
  const usFields = [
    ...new Set(school.programs.filter((p) => p.field).map((p) => fieldName(p.field!))),
  ]
  const th = 'px-3 py-2 text-left font-medium whitespace-nowrap'
  const td = 'px-3 py-2 whitespace-nowrap'
  const blockLabel = {
    institution: t.blockInstitution,
    admission: t.blockAdmission,
    cost: t.blockCost,
    stat: t.blockStat,
    strength: t.blockStrength,
  }

  return (
    <div className="lg:flex lg:gap-8">
      <SchoolToc items={toc} label={t.toc} />
      <div className="min-w-0 flex-1 space-y-10 pt-4 lg:pt-0">
        <section id="summary" className="scroll-mt-16 space-y-3">
          <h1 className="text-2xl font-bold break-words">{name}</h1>
          {other && <p className="text-subtle break-words">{other}</p>}
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            <dt className="text-subtle">{t.country}</dt>
            <dd>{i.country === 'TW' ? dict.explore.countryTW : dict.explore.countryUS}</dd>
            {place && (
              <>
                <dt className="text-subtle">{t.location}</dt>
                <dd>{place}</dd>
              </>
            )}
            {i.control && (
              <>
                <dt className="text-subtle">{t.control}</dt>
                <dd>{dict.explore[i.control]}</dd>
              </>
            )}
            {i.webUrl && (
              <>
                <dt className="text-subtle">{t.website}</dt>
                <dd className="break-all">
                  <a href={i.webUrl} target="_blank" rel="noopener noreferrer" className="text-brand underline">
                    {i.webUrl}
                  </a>
                </dd>
              </>
            )}
          </dl>
          <div className="flex flex-wrap gap-3">
            <FavoriteButton institutionId={i.id} labels={{ add: t.favorite, remove: t.unfavorite }} />
            {school.us && (
              <Link
                href={`/${locale}/programs/${school.us.allProgramId}`}
                prefetch={false}
                className="rounded border border-line px-3 py-1 text-sm hover:border-brand"
              >
                {t.addCompare}
              </Link>
            )}
          </div>
          <SourceNote name={i.source.name} url={i.source.url} fetchedAt={i.fetchedAt} locale={locale} labels={labels} />
        </section>

        <section id="admissions" className="scroll-mt-16 space-y-3">
          <h2 className="text-xl font-semibold">{t.admissions}</h2>
          {school.us ? (
            <>
              {school.us.years.length === 0 ||
              school.us.years.every((y) => y.admissionRate === null && y.sat === null && y.act === null) ? (
                <NoData label={dict.common.noData} />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <caption className="pb-1 text-left text-xs text-subtle">{t.percentileNote}</caption>
                    <thead>
                      <tr className="border-b border-line">
                        <th className={th}>{t.year}</th>
                        <th className={th}>{t.admissionRate}</th>
                        <th className={th}>{t.satRw}</th>
                        <th className={th}>{t.satMath}</th>
                        <th className={th}>{t.satTotal}</th>
                        <th className={th}>{t.act}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {school.us.years.map((y) => (
                        <tr key={y.year} className="border-b border-line">
                          <td className={td}>{y.year}</td>
                          <td className={td}>{formatPercent(y.admissionRate, locale)}</td>
                          <td className={td}>{formatRange(y.sat?.rw ?? null)}</td>
                          <td className={td}>{formatRange(y.sat?.math ?? null)}</td>
                          <td className={td}>{formatRange(y.sat?.total ?? null)}</td>
                          <td className={td}>{formatRange(y.act?.composite ?? null)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              {usFields.length > 0 && (
                <p className="text-sm">
                  <span className="text-subtle">{t.usFields}{locale === 'zh' ? '：' : ': '}</span>
                  {usFields.join(locale === 'zh' ? '、' : ', ')}
                </p>
              )}
              {school.us.source && school.us.fetchedAt && (
                <SourceNote
                  name={school.us.source.name}
                  url={school.us.source.url}
                  fetchedAt={school.us.fetchedAt}
                  locale={locale}
                  labels={labels}
                />
              )}
            </>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      <th className={th}>{t.programName}</th>
                      <th className={th}>{t.field}</th>
                      <th className={th}>{t.badgeApply}</th>
                      <th className={th}>{t.badgeSieve}</th>
                      <th className={th}>{t.badgeDistribution}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {school.programs.map((p) => {
                      const none = !p.hasApply && !p.hasSieve && !p.hasDistribution
                      return (
                        <tr key={p.id} className="border-b border-line">
                          <td className="px-3 py-2">
                            <Link href={`/${locale}/programs/${p.id}`} prefetch={false} className="text-brand hover:underline">
                              {displayName(locale, p.nameZh, p.nameEn)}
                            </Link>
                          </td>
                          <td className={td}>{p.field ? fieldName(p.field) : '—'}</td>
                          {none ? (
                            <td className={`${td} text-subtle`} colSpan={3}>
                              {dict.common.noData}
                            </td>
                          ) : (
                            <>
                              <Badge on={p.hasApply} label={t.badgeApply} className={td} />
                              <Badge on={p.hasSieve} label={t.badgeSieve} className={td} />
                              <Badge on={p.hasDistribution} label={t.badgeDistribution} className={td} />
                            </>
                          )}
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
              {school.twSources.map((s) => (
                <SourceNote key={s.name} name={s.name} url={s.url} fetchedAt={s.fetchedAt} locale={locale} labels={labels} />
              ))}
            </>
          )}
        </section>

        <section id="strengths" className="scroll-mt-16 space-y-3">
          <h2 className="text-xl font-semibold">{t.strengths}</h2>
          <StrengthList strengths={school.strengths} locale={locale} dict={dict} />
          {school.strengths.source && school.strengths.fetchedAt && (
            <SourceNote
              name={school.strengths.source.name}
              url={school.strengths.source.url}
              fetchedAt={school.strengths.fetchedAt}
              locale={locale}
              labels={labels}
            />
          )}
        </section>

        <section id="costs" className="scroll-mt-16 space-y-3">
          <h2 className="text-xl font-semibold">{t.costs}</h2>
          {i.country === 'US' && school.costs.length > 0 ? (
            <>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-line">
                      <th className={th}>{t.year}</th>
                      <th className={th}>{t.local}</th>
                      <th className={th}>{t.outOfState}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {school.costs.map((c) => (
                      <tr key={c.year} className="border-b border-line">
                        <td className={td}>{c.year}</td>
                        <td className={td}>{formatMoney(c.local, c.currency, locale)}</td>
                        <td className={td}>{formatMoney(c.outOfState, c.currency, locale)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-subtle">{t.costNote}</p>
              {school.costSource && (
                <SourceNote
                  name={school.costSource.name}
                  url={school.costSource.url}
                  fetchedAt={school.costSource.fetchedAt}
                  locale={locale}
                  labels={labels}
                />
              )}
            </>
          ) : (
            <NoData label={dict.common.noData} />
          )}
          {school.stat && (
            <div className="space-y-1">
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                {school.stat.studentSize !== null && (
                  <>
                    <dt className="text-subtle">{t.students}</dt>
                    <dd>{school.stat.studentSize.toLocaleString(locale === 'zh' ? 'zh-TW' : 'en-US')}</dd>
                  </>
                )}
                {school.stat.completionRate !== null && (
                  <>
                    <dt className="text-subtle">{t.completion}</dt>
                    <dd>{formatPercent(school.stat.completionRate, locale)}</dd>
                  </>
                )}
                {school.stat.medianEarnings !== null && (
                  <>
                    <dt className="text-subtle">{t.earnings}</dt>
                    <dd>{formatMoney(school.stat.medianEarnings, school.stat.currency ?? 'USD', locale)}</dd>
                  </>
                )}
              </dl>
              <p className="text-xs text-subtle">{t.statYear.replace('{year}', String(school.stat.year))}</p>
              <SourceNote
                name={school.stat.source.name}
                url={school.stat.source.url}
                fetchedAt={school.stat.fetchedAt}
                locale={locale}
                labels={labels}
              />
            </div>
          )}
        </section>

        <section id="sources" className="scroll-mt-16 space-y-3">
          <h2 className="text-xl font-semibold">{t.sources}</h2>
          <ul className="space-y-2">
            {school.sources.map((s) => (
              <li key={`${s.block}-${s.name}`} className="text-sm">
                <span className="font-medium">{blockLabel[s.block]}</span>
                <SourceNote name={s.name} url={s.url} fetchedAt={s.fetchedAt} locale={locale} labels={labels} />
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  )
}

function Badge({ on, label, className }: { on: boolean; label: string; className: string }) {
  return (
    <td className={className}>
      {on ? <span className="rounded border border-line px-2 py-0.5 text-xs">{label}</span> : <span className="text-subtle">—</span>}
    </td>
  )
}
