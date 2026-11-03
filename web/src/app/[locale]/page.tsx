import Link from 'next/link'
import { notFound } from 'next/navigation'
import { hasLocale } from '@/i18n/config'
import { getDictionary } from '@/i18n/dictionaries'

export default async function HomePage({ params }: PageProps<'/[locale]'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  const regions = [
    { key: 'tw', label: dict.region.tw },
    { key: 'us', label: dict.region.us },
    { key: 'all', label: dict.region.all },
  ] as const
  return (
    <div className="space-y-8">
      <section className="space-y-3">
        <h1 className="text-3xl font-bold">{dict.site.name}</h1>
        <p className="text-[var(--color-muted)]">{dict.site.tagline}</p>
        <form action={`/${locale}/explore`} method="get" className="flex gap-2">
          <input
            type="search"
            name="q"
            placeholder={dict.home.searchPlaceholder}
            aria-label={dict.home.searchPlaceholder}
            className="flex-1 rounded border border-[var(--color-border)] px-3 py-2"
          />
          <button type="submit" className="rounded bg-[var(--color-accent)] px-4 py-2 text-white">
            {dict.home.searchButton}
          </button>
        </form>
      </section>
      <section className="space-y-3">
        <h2 className="text-xl font-semibold">{dict.home.browseByRegion}</h2>
        <div className="flex gap-3">
          {regions.map((r) => (
            <Link
              key={r.key}
              href={`/${locale}/explore?region=${r.key}`}
              prefetch={false}
              className="rounded border border-[var(--color-border)] px-4 py-2 hover:border-[var(--color-accent)]"
            >
              {r.label}
            </Link>
          ))}
        </div>
      </section>
    </div>
  )
}
