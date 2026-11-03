import 'server-only'
import { sql } from '@/db/client'
import type { SieveStep, TwApplyRequirement, UacSubject } from '@/db/types'
import { getUsAdmission, type UsAdmission } from './school'

type Src = { name: string; url: string }

export type ProgramDetail = {
  program: {
    id: number
    code: string | null
    nameZh: string | null
    nameEn: string | null
    field: { code: string; nameZh: string; nameEn: string } | null
    source: Src
    fetchedAt: string
  }
  institution: {
    id: number
    country: 'TW' | 'US'
    nameZh: string | null
    nameEn: string | null
    webUrl: string | null
  }
  twApply: { year: number; requirement: TwApplyRequirement; source: Src; fetchedAt: string }[]
  twSieve: { year: number; steps: SieveStep[]; tiebreak: string | null; source: Src; fetchedAt: string }[]
  twDistribution: {
    year: number
    minScore: number | null
    admittedCount: number | null
    subjects: UacSubject[]
    tiebreak: string | null
    source: Src
    fetchedAt: string
  }[]
  /** US programs always show the school-level ('all') data. */
  us: (UsAdmission & { isSchoolLevel: true }) | null
}

const iso = (d: Date | string) => new Date(d).toISOString()

/** Taiwan programs with CAC application data: first `limit` ids, or [1] when none. */
export async function listProgramIdsForPrerender(limit: number): Promise<number[]> {
  const rows = await sql<{ id: number }[]>`
    select p.id from program p
    join institution i on i.id = p.institution_id
    where i.country_code = 'TW'
      and (exists (select 1 from admission_requirement r where r.program_id = p.id and r.pathway = 'tw_apply')
        or exists (select 1 from admission_stat a where a.program_id = p.id and a.pathway = 'tw_apply'))
    order by p.id limit ${limit}`
  return rows.length ? rows.map((r) => r.id) : [1]
}

type Row = { fetched_at: Date | string; source_name: string; source_url: string }

export async function getProgram(id: number): Promise<ProgramDetail | null> {
  const [p] = await sql<
    {
      id: number
      code: string | null
      name_zh: string | null
      name_en: string | null
      field_code: string | null
      f_zh: string | null
      f_en: string | null
      source_name: string
      source_url: string
      fetched_at: Date | string
      inst_id: number
      country_code: 'TW' | 'US'
      i_zh: string | null
      i_en: string | null
      web_url: string | null
    }[]
  >`
    select p.id, p.code, p.name_zh, p.name_en, p.field_code, f.name_zh as f_zh, f.name_en as f_en,
           s.name as source_name, s.url as source_url, p.fetched_at,
           i.id as inst_id, i.country_code, i.name_zh as i_zh, i.name_en as i_en, i.web_url
    from program p
    join institution i on i.id = p.institution_id
    join source s on s.id = p.source_id
    left join field f on f.code = p.field_code
    where p.id = ${id}`
  if (!p) return null

  const base = {
    program: {
      id: p.id,
      code: p.code,
      nameZh: p.name_zh,
      nameEn: p.name_en,
      field: p.field_code && p.f_zh !== null && p.f_en !== null ? { code: p.field_code, nameZh: p.f_zh, nameEn: p.f_en } : null,
      source: { name: p.source_name, url: p.source_url },
      fetchedAt: iso(p.fetched_at),
    },
    institution: { id: p.inst_id, country: p.country_code, nameZh: p.i_zh, nameEn: p.i_en, webUrl: p.web_url },
  }

  if (p.country_code === 'US') {
    const [all] = await sql<{ id: number }[]>`
      select id from program where institution_id = ${p.inst_id} and code = 'all' limit 1`
    const us = all ? { ...(await getUsAdmission(all.id)), isSchoolLevel: true as const } : null
    return { ...base, twApply: [], twSieve: [], twDistribution: [], us }
  }

  const applyRows = await sql<(Row & { year: number; requirement: TwApplyRequirement })[]>`
    select * from (
      select distinct on (r.year) r.year, r.requirement, s.name as source_name, r.source_url, r.fetched_at
      from admission_requirement r join source s on s.id = r.source_id
      where r.program_id = ${id} and r.pathway = 'tw_apply'
      order by r.year, r.fetched_at desc, r.id desc) x
    order by year desc limit 3`
  const sieveRows = await sql<(Row & { year: number; sieve: SieveStep[]; tiebreak: string | null })[]>`
    select * from (
      select distinct on (a.year) a.year, a.sieve, a.tiebreak, s.name as source_name, a.source_url, a.fetched_at
      from admission_stat a join source s on s.id = a.source_id
      where a.program_id = ${id} and a.pathway = 'tw_apply' and a.sieve is not null and jsonb_array_length(a.sieve) > 0
      order by a.year, a.fetched_at desc, a.id desc) x
    order by year desc limit 3`
  const distRows = await sql<
    (Row & { year: number; min_score: number | null; admitted_count: number | null; subjects: UacSubject[] | null; tiebreak: string | null })[]
  >`
    select * from (
      select distinct on (a.year) a.year, a.min_score::float8 as min_score, a.admitted_count, a.subjects, a.tiebreak,
             s.name as source_name, a.source_url, a.fetched_at
      from admission_stat a join source s on s.id = a.source_id
      where a.program_id = ${id} and a.pathway = 'tw_distribution'
      order by a.year, a.fetched_at desc, a.id desc) x
    order by year desc limit 3`

  const src = (r: Row): Src => ({ name: r.source_name, url: r.source_url })
  return {
    ...base,
    twApply: applyRows.map((r) => ({ year: r.year, requirement: r.requirement, source: src(r), fetchedAt: iso(r.fetched_at) })),
    twSieve: sieveRows.map((r) => ({
      year: r.year,
      steps: r.sieve,
      tiebreak: r.tiebreak,
      source: src(r),
      fetchedAt: iso(r.fetched_at),
    })),
    twDistribution: distRows.map((r) => ({
      year: r.year,
      minScore: r.min_score,
      admittedCount: r.admitted_count,
      subjects: r.subjects ?? [],
      tiebreak: r.tiebreak,
      source: src(r),
      fetchedAt: iso(r.fetched_at),
    })),
    us: null,
  }
}
