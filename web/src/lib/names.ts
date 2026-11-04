import type { Locale } from '@/i18n/config'

/** zh shows name_zh ?? name_en, en shows name_en ?? name_zh, neither -> "—". */
export function displayName(locale: Locale, zh: string | null, en: string | null): string {
  return (locale === 'zh' ? (zh ?? en) : (en ?? zh)) ?? '—'
}
