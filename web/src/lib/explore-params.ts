export const PAGE_SIZE = 20
export const MAX_PAGE = 500
export const MAX_Q = 100

export type ExploreParams = {
  q: string | null
  region: 'tw' | 'us' | 'all'
  field: string | null
  control: 'public' | 'private' | null
  maxTuition: number | null
  size: 'small' | 'medium' | 'large' | null
  page: number
}

type RawParams = Record<string, string | string[] | undefined>

const first = (v: string | string[] | undefined): string | undefined => (Array.isArray(v) ? v[0] : v)
const pick = <T extends string>(v: string | undefined, allowed: readonly T[]): T | null =>
  allowed.includes(v as T) ? (v as T) : null

/** Normalises untrusted URL params; the output is also the cache key, so it is tightly bounded. */
export function parseExploreParams(sp: RawParams, fieldCodes: readonly string[]): ExploreParams {
  const q = first(sp.q)?.trim().slice(0, MAX_Q).trim() || null
  const maxRaw = first(sp.maxTuition)
  const max = maxRaw !== undefined && /^\d{1,9}$/.test(maxRaw) ? Number(maxRaw) : 0
  const pageRaw = first(sp.page)
  const page = pageRaw !== undefined && /^-?\d{1,9}$/.test(pageRaw) ? Number(pageRaw) : 1
  return {
    q,
    region: pick(first(sp.region), ['tw', 'us'] as const) ?? 'all',
    field: pick(first(sp.field), fieldCodes),
    control: pick(first(sp.control), ['public', 'private'] as const),
    maxTuition: max > 0 ? max : null,
    size: pick(first(sp.size), ['small', 'medium', 'large'] as const),
    page: Math.min(MAX_PAGE, Math.max(1, page)),
  }
}

/** Query string (no leading "?") with only non-default values. */
export function toQueryString(p: ExploreParams, overrides: Partial<ExploreParams> = {}): string {
  const m = { ...p, ...overrides }
  const u = new URLSearchParams()
  if (m.q) u.set('q', m.q)
  if (m.region !== 'all') u.set('region', m.region)
  if (m.field) u.set('field', m.field)
  if (m.control) u.set('control', m.control)
  if (m.maxTuition) u.set('maxTuition', String(m.maxTuition))
  if (m.size) u.set('size', m.size)
  if (m.page > 1) u.set('page', String(m.page))
  return u.toString()
}
