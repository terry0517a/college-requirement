import 'server-only'
import { sql } from '@/db/client'
import type { SieveStep } from '@/db/types'
import { getProgram } from './program'

type Range = { p25: number; p75: number } | null
type Prov = { name: string; url: string; fetchedAt: string }

export type CompareItem = {
  programId: number
  programNameZh: string | null
  programNameEn: string | null
  institution: {
    id: number
    country: 'TW' | 'US'
    nameZh: string | null
    nameEn: string | null
    control: 'public' | 'private' | null
  }
  field: { code: string; nameZh: string; nameEn: string } | null
  requirementSummary:
    | { kind: 'tw_apply'; year: number; sieve: SieveStep[] }
    | { kind: 'us_sat'; year: number; satTotal: Range; act: Range }
    | null
  admission:
    | { kind: 'tw_distribution'; series: { year: number; minScore: number | null }[] }
    | { kind: 'us_rate'; series: { year: number; rate: number | null }[] }
    | null
  tuition: { year: number; local: number | null; outOfState: number | null; currency: string } | null
  topStrengthFields: string[]
  sources: Prov[]
}

const iso = (d: Date | string) => new Date(d).toISOString()

/** Programs in input order; ids that do not exist are skipped. */
export async function getCompareItems(ids: number[]): Promise<CompareItem[]> {
  const items: CompareItem[] = []
  for (const id of ids) {
    const d = await getProgram(id)
    if (!d) continue
    const instId = d.institution.id

    const [inst] = await sql<{ control: 'public' | 'private' | null }[]>`
      select control from institution where id = ${instId}`
    const [cost] = await sql<
      { year: number; local: number | null; oos: number | null; currency: string }[]
    >`
      select c.year,
        max(c.tuition) filter (where c.residency = 'local')::float8 as local,
        max(c.tuition) filter (where c.residency = 'out_of_state')::float8 as oos,
        max(c.currency) as currency
      from cost c
      where c.institution_id = ${instId} and c.residency in ('local', 'out_of_state')
      group by c.year order by c.year desc limit 1`
    const costSrc = cost
      ? await sql<{ name: string; url: string; fetched_at: Date | string }[]>`
          select s.name, c.source_url as url, max(c.fetched_at) as fetched_at
          from cost c join source s on s.id = c.source_id
          where c.institution_id = ${instId} and c.residency in ('local', 'out_of_state') and c.year = ${cost.year}
          group by s.id, s.name, c.source_url order by s.id, c.source_url`
      : []
    const strengthRows = await sql<{ name: string }[]>`
      select st.field_name as name
      from strength st
      where st.institution_id = ${instId}
      group by st.field_name order by sum(st.works_count) desc, st.field_name limit 3`
    const [strSrc] = strengthRows.length
      ? await sql<{ name: string; url: string; fetched_at: Date | string }[]>`
          select s.name, x.source_url as url, x.fetched_at
          from strength x join source s on s.id = x.source_id
          where x.institution_id = ${instId} order by x.fetched_at desc, x.id limit 1`
      : []

    let requirementSummary: CompareItem['requirementSummary'] = null
    let admission: CompareItem['admission'] = null
    const provs: Prov[] = [{ ...d.program.source, fetchedAt: d.program.fetchedAt }]

    if (d.institution.country === 'US') {
      const y = d.us?.years[0]
      if (y) requirementSummary = { kind: 'us_sat', year: y.year, satTotal: y.sat?.total ?? null, act: y.act?.composite ?? null }
      if (d.us && d.us.years.length) {
        admission = { kind: 'us_rate', series: d.us.years.map((x) => ({ year: x.year, rate: x.admissionRate })) }
        provs.push(...d.us.sources)
      }
    } else {
      const s = d.twSieve[0]
      if (s) {
        requirementSummary = { kind: 'tw_apply', year: s.year, sieve: s.steps }
        provs.push({ ...s.source, fetchedAt: s.fetchedAt })
      }
      if (d.twDistribution.length) {
        admission = { kind: 'tw_distribution', series: d.twDistribution.map((x) => ({ year: x.year, minScore: x.minScore })) }
        for (const x of d.twDistribution) provs.push({ ...x.source, fetchedAt: x.fetchedAt })
      }
    }
    for (const r of costSrc) provs.push({ name: r.name, url: r.url, fetchedAt: iso(r.fetched_at) })
    if (strSrc) provs.push({ name: strSrc.name, url: strSrc.url, fetchedAt: iso(strSrc.fetched_at) })

    // one entry per distinct (name, url), keeping the latest fetch time
    const m = new Map<string, Prov>()
    for (const p of provs) {
      const k = `${p.name}\n${p.url}`
      const cur = m.get(k)
      if (!cur || p.fetchedAt > cur.fetchedAt) m.set(k, p)
    }

    items.push({
      programId: d.program.id,
      programNameZh: d.program.nameZh,
      programNameEn: d.program.nameEn,
      institution: {
        id: instId,
        country: d.institution.country,
        nameZh: d.institution.nameZh,
        nameEn: d.institution.nameEn,
        control: inst?.control ?? null,
      },
      field: d.program.field,
      requirementSummary,
      admission,
      tuition: cost ? { year: cost.year, local: cost.local, outOfState: cost.oos, currency: cost.currency } : null,
      topStrengthFields: strengthRows.map((r) => r.name),
      sources: [...m.values()],
    })
  }
  return items
}
