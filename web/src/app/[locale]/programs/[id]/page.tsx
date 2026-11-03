import type { Metadata } from 'next'
import Link from 'next/link'
import { notFound } from 'next/navigation'
import { hasLocale, locales, type Locale } from '@/i18n/config'
import { getDictionary, type Dictionary } from '@/i18n/dictionaries'
import { getProgramCached, listProgramIdsForPrerender } from '@/lib/data'
import { displayName } from '@/lib/names'
import type { ProgramDetail } from '@/lib/queries/program'
import { safeHttpUrl } from '@/lib/url'
import { parseId } from '@/lib/ids'
import CompareButton from '@/components/CompareButton'
import DistributionTable from '@/components/DistributionTable'
import NoData from '@/components/NoData'
import SieveTable from '@/components/SieveTable'
import SourceNote from '@/components/SourceNote'
import TwApplyRequirement from '@/components/TwApplyRequirement'
import UsAdmissionTable from '@/components/UsAdmissionTable'

export async function generateStaticParams() {
  const ids = await listProgramIdsForPrerender(20)
  return locales.flatMap((locale) => ids.map((id) => ({ locale, id: String(id) })))
}

export async function generateMetadata({ params }: PageProps<'/[locale]/programs/[id]'>): Promise<Metadata> {
  const { locale, id: raw } = await params
  if (!hasLocale(locale)) notFound()
  const id = parseId(raw)
  if (id === null) notFound()
  const detail = await getProgramCached(id)
  if (!detail) notFound()
  return {
    title: displayName(locale, detail.program.nameZh, detail.program.nameEn),
    alternates: { languages: { 'zh-Hant-TW': `/zh/programs/${id}`, en: `/en/programs/${id}` } },
  }
}

// notFound() runs here, before any <Suspense>, so bad ids get a real 404.
export default async function ProgramPage({ params }: PageProps<'/[locale]/programs/[id]'>) {
  const { locale, id: raw } = await params
  if (!hasLocale(locale)) notFound()
  const id = parseId(raw)
  if (id === null) notFound()
  const detail = await getProgramCached(id)
  if (!detail) notFound()
  const dict = await getDictionary(locale)
  return <ProgramView detail={detail} locale={locale} dict={dict} />
}

type Prov = { name: string; url: string; fetchedAt: string }

/** Every distinct (source name, url) among the displayed rows, with that source's latest fetch time. */
function provenance(rows: { source: { name: string; url: string }; fetchedAt: string }[]): Prov[] {
  const m = new Map<string, Prov>()
  for (const r of rows) {
    const k = `${r.source.name}\n${r.source.url}`
    const cur = m.get(k)
    if (!cur || r.fetchedAt > cur.fetchedAt) m.set(k, { ...r.source, fetchedAt: r.fetchedAt })
  }
  return [...m.values()]
}

function ProgramView({ detail, locale, dict }: { detail: ProgramDetail; locale: Locale; dict: Dictionary }) {
  const t = dict.program
  const labels = { source: dict.common.source, fetched: dict.common.fetchedAt }
  const p = detail.program
  const i = detail.institution
  const name = displayName(locale, p.nameZh, p.nameEn)
  const webUrl = safeHttpUrl(i.webUrl)
  const schoolName = displayName(locale, i.nameZh, i.nameEn)
  const notes = (rows: Prov[]) =>
    rows.map((x) => (
      <SourceNote key={`${x.name}-${x.url}`} name={x.name} url={x.url} fetchedAt={x.fetchedAt} locale={locale} labels={labels} />
    ))
  const latest = detail.twApply[0]
  const h2 = 'text-xl font-semibold'

  return (
    <div className="min-w-0 space-y-10 pt-4">
      <section className="space-y-3">
        <h1 className="text-2xl font-bold break-words">{name}</h1>
        <p className="break-words">
          <Link href={`/${locale}/schools/${i.id}`} prefetch={false} className="text-brand hover:underline">
            {schoolName}
          </Link>
          {webUrl && (
            <>
              {' · '}
              <a href={webUrl} target="_blank" rel="noopener noreferrer" className="text-sm break-all text-subtle underline">
                {webUrl}
              </a>
            </>
          )}
        </p>
        <CompareButton programId={p.id} labels={dict.compare} />
        <SourceNote name={p.source.name} url={p.source.url} fetchedAt={p.fetchedAt} locale={locale} labels={labels} />
      </section>

      {i.country === 'US' ? (
        <section className="space-y-3">
          <h2 className={h2}>{dict.school.admissions}</h2>
          <p className="text-sm text-subtle">{t.usSchoolLevel}</p>
          {detail.us ? <UsAdmissionTable us={detail.us} locale={locale} dict={dict} /> : <NoData label={dict.common.noData} />}
        </section>
      ) : (
        <>
          <section id="apply" className="scroll-mt-16 space-y-3">
            <h2 className={h2}>{t.apply}</h2>
            {latest ? (
              <>
                <h3 className="font-medium">{t.applyYear.replace('{year}', String(latest.year))}</h3>
                <TwApplyRequirement requirement={latest.requirement} locale={locale} dict={dict} />
                {notes(provenance([latest]))}
              </>
            ) : (
              <NoData label={dict.common.noData} />
            )}
          </section>

          <section id="sieve" className="scroll-mt-16 space-y-3">
            <h2 className={h2}>{t.sieveHistory}</h2>
            {detail.twSieve.length > 0 ? (
              <>
                <SieveTable rows={detail.twSieve} dict={dict} />
                {notes(provenance(detail.twSieve))}
              </>
            ) : (
              <NoData label={dict.common.noData} />
            )}
          </section>

          <section id="distribution" className="scroll-mt-16 space-y-3">
            <h2 className={h2}>{t.distribution}</h2>
            {detail.twDistribution.length > 0 ? (
              <>
                <DistributionTable rows={detail.twDistribution} dict={dict} locale={locale} />
                <p className="text-xs text-subtle">{t.distNote}</p>
                {notes(provenance(detail.twDistribution))}
              </>
            ) : (
              <NoData label={dict.common.noData} />
            )}
          </section>
        </>
      )}
    </div>
  )
}
