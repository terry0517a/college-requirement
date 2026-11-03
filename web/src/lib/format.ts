import type { Locale } from '@/i18n/config'

const DASH = '—'
const intlLocale: Record<Locale, string> = { zh: 'zh-TW', en: 'en-US' }

const dateParts = new Intl.DateTimeFormat('en-CA', {
  timeZone: 'Asia/Taipei',
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
})

/** YYYY-MM-DD in Asia/Taipei, whatever the viewer's locale. */
export function formatDate(d: Date | string, locale: Locale): string {
  void locale
  return dateParts.format(typeof d === 'string' ? new Date(d) : d)
}

export function formatMoney(n: number | null, currency: string, locale: Locale): string {
  if (n === null) return DASH
  return new Intl.NumberFormat(intlLocale[locale], {
    style: 'currency',
    currency,
    maximumFractionDigits: 0,
  }).format(n)
}

/** 0.0361 -> "3.6%" */
export function formatPercent(r: number | null, locale: Locale): string {
  void locale
  return r === null ? DASH : `${(r * 100).toFixed(1)}%`
}

export function formatRange(r: { p25: number; p75: number } | null): string {
  return r === null ? DASH : `${r.p25}–${r.p75}`
}

/** List separator: 、 for zh, ", " for en. */
export function listSep(locale: Locale): string {
  return locale === 'zh' ? '、' : ', '
}
