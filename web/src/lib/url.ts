/** Returns a trimmed http(s) URL, or null for anything else (javascript:, data:, relative, empty, non-string). */
export function safeHttpUrl(u: unknown): string | null {
  if (typeof u !== 'string') return null
  const s = u.trim()
  if (!s) return null
  try {
    const p = new URL(s).protocol
    return p === 'http:' || p === 'https:' ? s : null
  } catch {
    return null
  }
}
