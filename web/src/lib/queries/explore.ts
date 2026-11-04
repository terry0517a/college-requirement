import 'server-only'
import { sql } from '@/db/client'
import type { Locale } from '@/i18n/config'
import { PAGE_SIZE, type ExploreParams } from '../explore-params'

export type ExploreItem = {
  id: number
  country: 'TW' | 'US'
  nameZh: string | null
  nameEn: string | null
  control: 'public' | 'private' | null
  city: string | null
  region: string | null
  programCount: number
  matchedPrograms: { id: number; nameZh: string | null; nameEn: string | null }[]
  tuition: {
    year: number
    local: number | null
    outOfState: number | null
    currency: string
    source: { name: string; url: string }
    fetchedAt: string
  } | null
  studentSize: number | null
  source: { name: string; url: string }
  fetchedAt: string
}

// 台 and 臺 are the same character to users: q is normalized to 台 and so are the zh columns.
const escapeLike = (s: string) => s.replace(/[\\%_]/g, '\\$&')

type Row = {
  id: number
  country_code: 'TW' | 'US'
  name_zh: string | null
  name_en: string | null
  control: 'public' | 'private' | null
  city: string | null
  region: string | null
  program_count: number
  matched: { id: number; nameZh: string | null; nameEn: string | null }[] | null
  t_year: number | null
  t_local: number | null
  t_oos: number | null
  t_currency: string | null
  t_source_name: string | null
  t_source_url: string | null
  t_fetched_at: Date | string | null
  student_size: number | null
  source_name: string
  source_url: string
  fetched_at: Date | string
}

export async function searchInstitutions(
  p: ExploreParams,
  locale: Locale,
): Promise<{ total: number; items: ExploreItem[] }> {
  const like = p.q ? `%${escapeLike(p.q.replaceAll('臺', '台'))}%` : null
  const progQ = like
    ? sql`and (translate(pr.name_zh, '臺', '台') ilike ${like} escape '\\' or pr.name_en ilike ${like} escape '\\')`
    : sql``
  const progField = p.field ? sql`and pr.field_code = ${p.field}` : sql``
  const showMatches = like !== null || p.field !== null

  const where = sql`
    exists (select 1 from program x where x.institution_id = i.id)
    ${p.region === 'all' ? sql`` : sql`and i.country_code = ${p.region === 'tw' ? 'TW' : 'US'}`}
    ${p.control ? sql`and i.control = ${p.control}` : sql``}
    ${
      like
        ? sql`and (translate(i.name_zh, '臺', '台') ilike ${like} escape '\\' or i.name_en ilike ${like} escape '\\'
            or exists (select 1 from program pr where pr.institution_id = i.id
              and (translate(pr.name_zh, '臺', '台') ilike ${like} escape '\\' or pr.name_en ilike ${like} escape '\\')))`
        : sql``
    }
    ${
      p.field
        ? sql`and exists (select 1 from program pf where pf.institution_id = i.id and pf.field_code = ${p.field})`
        : sql``
    }
    ${p.maxTuition ? sql`and i.country_code = 'US' and t.tuition is not null and t.tuition <= ${p.maxTuition}` : sql``}
    ${
      p.size === 'small'
        ? sql`and st.student_size < 5000`
        : p.size === 'medium'
          ? sql`and st.student_size between 5000 and 15000`
          : p.size === 'large'
            ? sql`and st.student_size > 15000`
            : sql``
    }`

  // Latest cost year (out_of_state preferred over local for filtering) and latest stat row.
  const joins = sql`
    from institution i
    join source s on s.id = i.source_id
    left join lateral (
      select c.year,
             max(c.tuition) filter (where c.residency = 'local')::float8 as local,
             max(c.tuition) filter (where c.residency = 'out_of_state')::float8 as oos,
             coalesce(
               max(c.tuition) filter (where c.residency = 'out_of_state'),
               max(c.tuition) filter (where c.residency = 'local'))::float8 as tuition,
             max(c.currency) as currency,
             (array_agg(cs.name order by (c.residency = 'out_of_state') desc))[1] as source_name,
             (array_agg(c.source_url order by (c.residency = 'out_of_state') desc))[1] as source_url,
             (array_agg(c.fetched_at order by (c.residency = 'out_of_state') desc))[1] as fetched_at
      from cost c
      join source cs on cs.id = c.source_id
      where c.institution_id = i.id and c.residency in ('local', 'out_of_state')
        and c.year = (select max(c2.year) from cost c2
                      where c2.institution_id = i.id and c2.residency in ('local', 'out_of_state'))
      group by c.year
    ) t on true
    left join lateral (
      select s2.student_size from institution_stat s2
      where s2.institution_id = i.id order by s2.year desc limit 1
    ) st on true`

  const name = locale === 'zh' ? sql`coalesce(i.name_zh, i.name_en)` : sql`coalesce(i.name_en, i.name_zh)`

  const [countRows, rows] = await Promise.all([
    sql<{ n: number }[]>`select count(*)::int as n ${joins} where ${where}`,
    sql<Row[]>`
      select i.id, i.country_code, i.name_zh, i.name_en, i.control, i.city, i.region,
             (select count(*)::int from program x where x.institution_id = i.id) as program_count,
             ${
               showMatches
                 ? sql`(select coalesce(json_agg(m), '[]'::json) from (
                     select pr.id, pr.name_zh as "nameZh", pr.name_en as "nameEn"
                     from program pr where pr.institution_id = i.id ${progQ} ${progField}
                     order by pr.id limit 3) m)`
                 : sql`null`
             } as matched,
             t.year as t_year, t.local as t_local, t.oos as t_oos, t.currency as t_currency,
             t.source_name as t_source_name, t.source_url as t_source_url, t.fetched_at as t_fetched_at,
             st.student_size,
             s.name as source_name, s.url as source_url, i.fetched_at
      ${joins}
      where ${where}
      order by i.country_code, ${name}, i.id
      limit ${PAGE_SIZE} offset ${(p.page - 1) * PAGE_SIZE}`,
  ])

  return {
    total: countRows[0]?.n ?? 0,
    items: rows.map((r) => ({
      id: r.id,
      country: r.country_code,
      nameZh: r.name_zh,
      nameEn: r.name_en,
      control: r.control,
      city: r.city,
      region: r.region,
      programCount: r.program_count,
      matchedPrograms: r.matched ?? [],
      tuition:
        r.t_year === null
          ? null
          : {
              year: r.t_year,
              local: r.t_local,
              outOfState: r.t_oos,
              currency: r.t_currency ?? 'USD',
              source: { name: r.t_source_name ?? '', url: r.t_source_url ?? '' },
              fetchedAt: new Date(r.t_fetched_at ?? r.fetched_at).toISOString(),
            },
      studentSize: r.student_size,
      source: { name: r.source_name, url: r.source_url },
      fetchedAt: new Date(r.fetched_at).toISOString(),
    })),
  }
}
