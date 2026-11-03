import type { MetadataRoute } from 'next'
import { locales } from '@/i18n/config'
import { listProgramIdsForPrerender, listSchoolIdsForPrerender } from '@/lib/data'
import { SITE_URL } from '@/lib/site-url'

// Stays under the 50,000-URL limit of one sitemap file: 2 locales x (4 static + schools + programs).
const MAX_SCHOOLS = 5000
const MAX_PROGRAMS = 15000

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [schoolIds, programIds] = await Promise.all([
    listSchoolIdsForPrerender(MAX_SCHOOLS),
    listProgramIdsForPrerender(MAX_PROGRAMS),
  ])
  const paths = [
    '',
    '/explore',
    '/compare',
    '/about',
    ...schoolIds.map((id) => `/schools/${id}`),
    ...programIds.map((id) => `/programs/${id}`),
  ]
  return paths.flatMap((path) =>
    locales.map((locale) => ({
      url: `${SITE_URL}/${locale}${path}`,
      alternates: {
        languages: {
          'zh-Hant-TW': `${SITE_URL}/zh${path}`,
          en: `${SITE_URL}/en${path}`,
        },
      },
    })),
  )
}
