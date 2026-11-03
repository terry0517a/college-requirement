import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import { hasLocale, type Locale } from '@/i18n/config'
import { getDictionary, type Dictionary } from '@/i18n/dictionaries'
import { parseExploreParams } from '@/lib/explore-params'
import { getFields, searchInstitutionsCached } from '@/lib/data'
import ExploreFilters from '@/components/ExploreFilters'
import InstitutionCard from '@/components/InstitutionCard'
import Pagination from '@/components/Pagination'

export default async function ExplorePage({ params, searchParams }: PageProps<'/[locale]/explore'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold">{dict.explore.title}</h1>
      <Suspense fallback={<p className="text-subtle">{dict.explore.loading}</p>}>
        <Results locale={locale} dict={dict} searchParams={searchParams} />
      </Suspense>
    </div>
  )
}

// The filter form lives inside the boundary too: its defaults come from searchParams.
async function Results({
  locale,
  dict,
  searchParams,
}: {
  locale: Locale
  dict: Dictionary
  searchParams: PageProps<'/[locale]/explore'>['searchParams']
}) {
  const fields = await getFields()
  const params = parseExploreParams(await searchParams, fields.map((f) => f.code))
  const { total, items } = await searchInstitutionsCached(params, locale)
  return (
    <>
      <ExploreFilters params={params} fields={fields} locale={locale} dict={dict} />
      <p className="text-sm text-subtle">{dict.explore.total.replace('{n}', total.toLocaleString())}</p>
      {items.length === 0 ? (
        <p>{dict.explore.empty}</p>
      ) : (
        <ul className="grid gap-4 md:grid-cols-2">
          {items.map((item) => (
            <InstitutionCard key={item.id} item={item} locale={locale} dict={dict} />
          ))}
        </ul>
      )}
      <Pagination params={params} total={total} locale={locale} dict={dict} />
    </>
  )
}
