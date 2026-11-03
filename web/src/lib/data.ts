import 'server-only'
import { cacheLife, cacheTag } from 'next/cache'
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
