import 'server-only'
import { cacheLife, cacheTag } from 'next/cache'
import type { Locale } from '@/i18n/config'
import type { ExploreParams } from './explore-params'
import { searchInstitutions } from './queries/explore'
import { listFields, listSources } from './queries/meta'
import { getSchool, listSchoolIdsForPrerender as listIds } from './queries/school'

// Every export: async, 'use cache', cacheLife + cacheTag, delegates to queries/*.
// Return values must be serializable (no bigint).

export async function getFields() {
  'use cache'
  cacheLife('days')
  cacheTag('fields')
  return listFields()
}

export async function getSources() {
  'use cache'
  cacheLife('days')
  cacheTag('sources')
  return listSources()
}

// Primitive args only (the caller passes the already-normalised params), so the
// cache key space stays bounded; ExploreParams is rebuilt inside.
export async function searchInstitutionsCached(
  q: string | null,
  region: ExploreParams['region'],
  field: string | null,
  control: ExploreParams['control'],
  maxTuition: number | null,
  size: ExploreParams['size'],
  page: number,
  locale: Locale,
) {
  'use cache'
  cacheLife('hours')
  cacheTag('institutions')
  return searchInstitutions({ q, region, field, control, maxTuition, size, page }, locale)
}

export async function getSchoolCached(id: number) {
  'use cache'
  cacheLife('hours')
  cacheTag('institutions', `school-${id}`)
  return getSchool(id)
}

export async function listSchoolIdsForPrerender(limit: number) {
  'use cache'
  cacheLife('days')
  cacheTag('institutions')
  return listIds(limit)
}
