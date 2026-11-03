import 'server-only'
import { cacheLife, cacheTag } from 'next/cache'
import type { Locale } from '@/i18n/config'
import type { ExploreParams } from './explore-params'
import { searchInstitutions } from './queries/explore'
import { listFields, listSources } from './queries/meta'

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

// Args are the already-normalised (whitelisted, clamped) explore params, so the
// cache key space stays bounded. Plain serializable object, no bigint.
export async function searchInstitutionsCached(params: ExploreParams, locale: Locale) {
  'use cache'
  cacheLife('hours')
  cacheTag('institutions')
  return searchInstitutions(params, locale)
}
