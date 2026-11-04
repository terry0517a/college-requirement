/** Positive int32 id from a URL segment / query value, else null. Safe to import anywhere (no server deps). */
export function parseId(raw: string): number | null {
  if (!/^[1-9][0-9]{0,9}$/.test(raw)) return null
  const n = Number(raw)
  return n <= 2147483647 ? n : null
}
