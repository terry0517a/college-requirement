import 'server-only'
import { asc } from 'drizzle-orm'
import { db } from '@/db/client'
import { field, source } from '@/db/schema'

export async function listFields(): Promise<
  { code: string; name_zh: string; name_en: string; sort: number }[]
> {
  const rows = await db.select().from(field).orderBy(asc(field.sort))
  return rows.map((r) => ({ code: r.code, name_zh: r.nameZh, name_en: r.nameEn, sort: r.sort }))
}

export async function listSources(): Promise<
  { id: number; code: string; name: string; url: string; license: string | null }[]
> {
  const rows = await db.select().from(source).orderBy(asc(source.id))
  return rows.map(({ id, code, name, url, license }) => ({ id, code, name, url, license }))
}
