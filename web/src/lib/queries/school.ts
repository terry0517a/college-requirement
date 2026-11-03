import 'server-only'
import { sql } from '@/db/client'
import type { UsSatRequirement } from '@/db/types'

type Src = { name: string; url: string }
export type Prov = Src & { fetchedAt: string }

export type SchoolDetail = {
  institution: {
    id: number
    country: 'TW' | 'US'
    nameZh: string | null
    nameEn: string | null
    control: 'public' | 'private' | null
    city: string | null
    region: string | null
    webUrl: string | null
    source: Src
    fetchedAt: string
  }
  programs: {
    id: number
    code: string | null
    nameZh: string | null
    nameEn: string | null
    field: { code: string; nameZh: string; nameEn: string } | null
    hasApply: boolean
    hasSieve: boolean
    hasDistribution: boolean
  }[]
  /** Taiwan only: provenance of the program table (one entry per source). */
  twSources: Prov[]
  us: UsAdmission | null
  costs: { year: number; local: number | null; outOfState: number | null; currency: string }[]
  costSources: Prov[]
  stat: {
    year: number
    studentSize: number | null
    completionRate: number | null
    medianEarnings: number | null
    currency: string | null
    source: Src
    fetchedAt: string
  } | null
  strengths: {
    fields: { name: string; works: number; rank: number; of: number }[]
    topics: { name: string; field: string; works: number }[]
    source: Src | null
    fetchedAt: string | null
  }
  sources: { block: 'institution' | 'admission' | 'cost' | 'stat' | 'strength'; name: string; url: string; fetchedAt: string }[]
}

export { parseId } from '@/lib/ids'

const iso = (d: Date | string) => new Date(d).toISOString()

export async function listSchoolIdsForPrerender(limit: number): Promise<number[]> {
  const rows = await sql<{ id: number }[]>`
    select i.id from institution i
    join program p on p.institution_id = i.id
    group by i.id order by count(*) desc, i.id limit ${limit}`
  return rows.length ? rows.map((r) => r.id) : [1]
}

type InstRow = {
  id: number
  country_code: 'TW' | 'US'
  name_zh: string | null
  name_en: string | null
  control: 'public' | 'private' | null
  city: string | null
  region: string | null
  web_url: string | null
  source_name: string
  source_url: string
  fetched_at: Date | string
}
type ProgRow = {
  id: number
  code: string | null
  name_zh: string | null
  name_en: string | null
  field_code: string | null
  f_zh: string | null
  f_en: string | null
  has_apply: boolean
  has_sieve: boolean
  has_dist: boolean
}
type ProvRow = { name: string; url: string; fetched_at: Date | string }

export type UsAdmission = {
  allProgramId: number
  years: {
    year: number
    admissionRate: number | null
    sat: UsSatRequirement['sat'] | null
    act: UsSatRequirement['act'] | null
  }[]
  sources: Prov[]
}

/** US school-level admission data (latest 3 years) hung off the 'all' program. */
export async function getUsAdmission(allProgramId: number): Promise<UsAdmission> {
  const years = await sql<
    { year: number; rate: number | null; sat: UsSatRequirement['sat'] | null; act: UsSatRequirement['act'] | null }[]
  >`
    with ys as (
      select year from admission_stat where program_id = ${allProgramId} and pathway = 'us_freshman'
      union
      select year from admission_requirement where program_id = ${allProgramId} and pathway = 'us_freshman'
      order by year desc limit 3)
    select ys.year,
      (select a.admission_rate::float8 from admission_stat a
        where a.program_id = ${allProgramId} and a.pathway = 'us_freshman' and a.year = ys.year
        order by a.fetched_at desc, a.id desc limit 1) as rate,
      (select r.requirement->'sat' from admission_requirement r
        where r.program_id = ${allProgramId} and r.pathway = 'us_freshman' and r.year = ys.year
        order by r.fetched_at desc, r.id desc limit 1) as sat,
      (select r.requirement->'act' from admission_requirement r
        where r.program_id = ${allProgramId} and r.pathway = 'us_freshman' and r.year = ys.year
        order by r.fetched_at desc, r.id desc limit 1) as act
    from ys order by ys.year desc`
  const srcs = await sql<{ name: string; url: string; fetched_at: Date | string }[]>`
    select s.name, x.source_url as url, max(x.fetched_at) as fetched_at from (
      select source_id, source_url, fetched_at, year from admission_stat
        where program_id = ${allProgramId} and pathway = 'us_freshman'
      union all
      select source_id, source_url, fetched_at, year from admission_requirement
        where program_id = ${allProgramId} and pathway = 'us_freshman') x
    join source s on s.id = x.source_id
    where x.year = any(${years.map((y) => y.year)})
    group by s.id, s.name, x.source_url order by s.id, x.source_url`
  return {
    allProgramId,
    years: years.map((y) => ({ year: y.year, admissionRate: y.rate, sat: y.sat, act: y.act })),
    sources: srcs.map((r) => ({ name: r.name, url: r.url, fetchedAt: iso(r.fetched_at) })),
  }
}

export async function getSchool(id: number): Promise<SchoolDetail | null> {
  const [inst] = await sql<InstRow[]>`
    select i.id, i.country_code, i.name_zh, i.name_en, i.control, i.city, i.region, i.web_url,
           s.name as source_name, s.url as source_url, i.fetched_at
    from institution i join source s on s.id = i.source_id
    where i.id = ${id} and exists (select 1 from program x where x.institution_id = i.id)`
  if (!inst) return null
  const country = inst.country_code

  const progs = await sql<ProgRow[]>`
    select p.id, p.code, p.name_zh, p.name_en, p.field_code, f.name_zh as f_zh, f.name_en as f_en,
      (exists (select 1 from admission_stat a where a.program_id = p.id and a.pathway = 'tw_apply')
        or exists (select 1 from admission_requirement r where r.program_id = p.id and r.pathway = 'tw_apply')) as has_apply,
      exists (select 1 from admission_stat a where a.program_id = p.id and a.pathway = 'tw_apply'
        and a.sieve is not null and jsonb_array_length(a.sieve) > 0) as has_sieve,
      exists (select 1 from admission_stat a where a.program_id = p.id and a.pathway = 'tw_distribution') as has_dist
    from program p left join field f on f.code = p.field_code
    where p.institution_id = ${id}
    order by (${country} = 'US' and p.code = 'all') desc,
             case when ${country} = 'US' then p.code end,
             coalesce(p.name_zh, p.name_en), p.id`

  const programs = progs.map((p) => ({
    id: p.id,
    code: p.code,
    nameZh: p.name_zh,
    nameEn: p.name_en,
    field: p.field_code && p.f_zh !== null && p.f_en !== null ? { code: p.field_code, nameZh: p.f_zh, nameEn: p.f_en } : null,
    hasApply: p.has_apply,
    hasSieve: p.has_sieve,
    hasDistribution: p.has_dist,
  }))

  // Taiwan: provenance of the program rows shown in the table.
  const twSourceRows =
    country === 'TW'
      ? await sql<ProvRow[]>`
          select s.name, s.url, max(p.fetched_at) as fetched_at
          from program p join source s on s.id = p.source_id
          where p.institution_id = ${id} group by s.id, s.name, s.url order by s.id`
      : []

  // US: school-level rows hang off the program with code 'all'.
  const allProgram = country === 'US' ? programs.find((p) => p.code === 'all') : undefined
  const us: SchoolDetail['us'] = allProgram ? await getUsAdmission(allProgram.id) : null

  const costRows = await sql<
    { year: number; local: number | null; oos: number | null; currency: string }[]
  >`
    select c.year,
      max(c.tuition) filter (where c.residency = 'local')::float8 as local,
      max(c.tuition) filter (where c.residency = 'out_of_state')::float8 as oos,
      max(c.currency) as currency
    from cost c
    where c.institution_id = ${id} and c.residency in ('local', 'out_of_state')
    group by c.year order by c.year desc limit 3`
  const costs = costRows.map((c) => ({ year: c.year, local: c.local, outOfState: c.oos, currency: c.currency }))
  const costSrcRows = costs.length
    ? await sql<ProvRow[]>`
        select s.name, c.source_url as url, max(c.fetched_at) as fetched_at
        from cost c join source s on s.id = c.source_id
        where c.institution_id = ${id} and c.residency in ('local', 'out_of_state')
          and c.year = any(${costs.map((c) => c.year)})
        group by s.id, s.name, c.source_url order by s.id, c.source_url`
    : []
  const costSources: Prov[] = costSrcRows.map((r) => ({ name: r.name, url: r.url, fetchedAt: iso(r.fetched_at) }))

  const [st] = await sql<
    {
      year: number
      student_size: number | null
      completion_rate: number | null
      median_earnings: number | null
      currency: string | null
      name: string
      url: string
      fetched_at: Date | string
    }[]
  >`
    select t.year, t.student_size, t.completion_rate::float8 as completion_rate,
           t.median_earnings::float8 as median_earnings, t.currency, s.name, t.source_url as url, t.fetched_at
    from institution_stat t join source s on s.id = t.source_id
    where t.institution_id = ${id} order by t.year desc limit 1`
  const stat: SchoolDetail['stat'] = st
    ? {
        year: st.year,
        studentSize: st.student_size,
        completionRate: st.completion_rate,
        medianEarnings: st.median_earnings,
        currency: st.currency,
        source: { name: st.name, url: st.url },
        fetchedAt: iso(st.fetched_at),
      }
    : null

  const fieldRows = await sql<{ name: string; works: number; rank: number; of: number }[]>`
    with t as (
      select st.institution_id, st.field_name, sum(st.works_count)::int as works
      from strength st
      where exists (select 1 from program p where p.institution_id = st.institution_id)
      group by st.institution_id, st.field_name),
    r as (
      select t.*, rank() over (partition by field_name order by works desc)::int as rk,
             count(*) over (partition by field_name)::int as n
      from t)
    select field_name as name, works, rk as rank, n as of from r
    where institution_id = ${id} order by works desc, field_name limit 5`
  const topicRows = await sql<{ name: string; field: string; works: number }[]>`
    select topic_name as name, field_name as field, works_count as works
    from strength where institution_id = ${id} order by rank, topic_name limit 10`
  const [ss] = await sql<ProvRow[]>`
    select s.name, x.source_url as url, x.fetched_at
    from strength x join source s on s.id = x.source_id
    where x.institution_id = ${id} order by x.fetched_at desc, x.id limit 1`
  const strengths: SchoolDetail['strengths'] = {
    fields: fieldRows,
    topics: topicRows,
    source: ss ? { name: ss.name, url: ss.url } : null,
    fetchedAt: ss ? iso(ss.fetched_at) : null,
  }

  const sources: SchoolDetail['sources'] = [
    { block: 'institution', name: inst.source_name, url: inst.source_url, fetchedAt: iso(inst.fetched_at) },
  ]
  for (const x of us?.sources ?? []) sources.push({ block: 'admission', ...x })
  const twSources = twSourceRows.map((r) => ({ name: r.name, url: r.url, fetchedAt: iso(r.fetched_at) }))
  for (const s of twSources) sources.push({ block: 'admission', ...s })
  for (const x of costSources) sources.push({ block: 'cost', ...x })
  if (stat) sources.push({ block: 'stat', ...stat.source, fetchedAt: stat.fetchedAt })
  if (strengths.source && strengths.fetchedAt) sources.push({ block: 'strength', ...strengths.source, fetchedAt: strengths.fetchedAt })

  return {
    institution: {
      id: inst.id,
      country,
      nameZh: inst.name_zh,
      nameEn: inst.name_en,
      control: inst.control,
      city: inst.city,
      region: inst.region,
      webUrl: inst.web_url,
      source: { name: inst.source_name, url: inst.source_url },
      fetchedAt: iso(inst.fetched_at),
    },
    programs,
    twSources,
    us,
    costs,
    costSources,
    stat,
    strengths,
    sources,
  }
}
