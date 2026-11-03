import Link from 'next/link'
import { notFound } from 'next/navigation'
import { hasLocale } from '@/i18n/config'
import { getDictionary } from '@/i18n/dictionaries'
import { getFields } from '@/lib/data'

export default async function HomePage({ params }: PageProps<'/[locale]'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  const fields = await getFields()
  const regions = [
    { key: 'tw', label: dict.region.tw },
    { key: 'us', label: dict.region.us },
    { key: 'all', label: dict.region.all },
  ] as const
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-3xl font-bold">{dict.site.name}</h1>
        <p className="text-subtle">{dict.site.tagline}</p>
        <form action={`/${locale}/explore`} method="get" className="flex gap-2">
          <input
            type="search"
            name="q"
            placeholder={dict.home.searchPlaceholder}
            aria-label={dict.home.searchPlaceholder}
            className="flex-1 rounded border border-line px-3 py-2"
          />
          <button type="submit" className="rounded bg-brand px-4 py-2 text-white">
            {dict.home.searchButton}
          </button>
        </form>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{dict.home.browseByRegion}</h2>
        <div className="flex flex-wrap gap-3">
          {regions.map((r) => (
            <Link
              key={r.key}
              href={`/${locale}/explore?region=${r.key}`}
              prefetch={false}
              className="rounded border border-line px-4 py-2 hover:border-brand"
            >
              {r.label}
            </Link>
          ))}
        </div>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{dict.home.browseByField}</h2>
        <ul className="flex flex-wrap gap-2">
          {fields.map((f) => (
            <li key={f.code}>
              <Link
                href={`/${locale}/explore?field=${encodeURIComponent(f.code)}`}
                prefetch={false}
                className="inline-block rounded border border-line px-3 py-1.5 text-sm hover:border-brand"
              >
                {locale === 'zh' ? f.name_zh : f.name_en}
              </Link>
            </li>
          ))}
        </ul>
      </section>
    </div>
  )
}
