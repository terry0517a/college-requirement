export const locales = ['zh', 'en'] as const
export type Locale = (typeof locales)[number]
export const defaultLocale: Locale = 'zh'

export function hasLocale(x: string): x is Locale {
  return (locales as readonly string[]).includes(x)
}

export const htmlLang: Record<Locale, string> = { zh: 'zh-Hant-TW', en: 'en' }
