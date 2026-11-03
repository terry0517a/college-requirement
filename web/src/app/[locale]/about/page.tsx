import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { hasLocale } from '@/i18n/config'
import { getDictionary } from '@/i18n/dictionaries'
import { getSources } from '@/lib/data'
import { safeHttpUrl } from '@/lib/url'

export async function generateMetadata({ params }: PageProps<'/[locale]/about'>): Promise<Metadata> {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  return {
    title: (await getDictionary(locale)).about.title,
    alternates: { languages: { 'zh-Hant-TW': '/zh/about', en: '/en/about' } },
  }
}

export default async function AboutPage({ params }: PageProps<'/[locale]/about'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  const t = dict.about
  const sources = await getSources()
  const schedule = [
    [t.scheduleHipo, t.scheduleHipoWhen],
    [t.scheduleOpenalex, t.scheduleOpenalexWhen],
    [t.scheduleUac, t.scheduleUacWhen],
    [t.scheduleScorecard, t.scheduleScorecardWhen],
    [t.scheduleCac, t.scheduleCacWhen],
  ]
  const h2 = 'text-xl font-semibold'
  const sep = locale === 'zh' ? '：' : ': '
  return (
    <div className="min-w-0 space-y-8">
      <h1 className="text-2xl font-bold">{t.title}</h1>
      <section className="space-y-2">
        <h2 className={h2}>{t.purposeTitle}</h2>
        <p>{t.purposeBody}</p>
      </section>
      <section className="space-y-3">
        <h2 className={h2}>{t.sourcesTitle}</h2>
        <p>{t.sourcesIntro}</p>
        <ul className="space-y-2">
          {sources.map((s) => {
            const href = safeHttpUrl(s.url)
            return (
              <li key={s.id} className="break-words">
                {href ? (
                  <a href={href} target="_blank" rel="noopener noreferrer" className="text-brand underline">
                    {s.name}
                  </a>
                ) : (
                  s.name
                )}
                <span className="block text-sm text-subtle">
                  {t.license}
                  {sep}
                  {s.license ?? t.noLicense}
                </span>
              </li>
            )
          })}
        </ul>
      </section>
      <section className="space-y-3">
        <h2 className={h2}>{t.scheduleTitle}</h2>
        <p>{t.scheduleIntro}</p>
        <ul className="space-y-1">
          {schedule.map(([name, when]) => (
            <li key={name} className="break-words">
              <span className="font-medium">{name}</span>
              {sep}
              {when}
            </li>
          ))}
        </ul>
      </section>
      <section className="space-y-2">
        <h2 className={h2}>{t.disclaimerTitle}</h2>
        <p>{t.disclaimerBody1}</p>
        <p>{t.disclaimerBody2}</p>
        <p>{t.disclaimerBody3}</p>
      </section>
      <section className="space-y-2">
        <h2 className={h2}>{t.privacyTitle}</h2>
        <p>{t.privacyBody}</p>
      </section>
    </div>
  )
}
