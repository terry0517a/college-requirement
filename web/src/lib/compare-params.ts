import { parseId } from './ids'

export const MAX_COMPARE = 4

/** `?ids=` value(s) -> up to MAX_COMPARE distinct valid ids, first-seen order. */
export function parseCompareIds(raw: string | string[] | undefined): number[] {
  const first = Array.isArray(raw) ? raw[0] : raw
  if (!first) return []
  const out: number[] = []
  for (const part of first.split(',')) {
    const id = parseId(part.trim())
    if (id !== null && !out.includes(id)) out.push(id)
    if (out.length >= MAX_COMPARE) break
  }
  return out
}
