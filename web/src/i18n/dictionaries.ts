import 'server-only'
import type { Locale } from './config'

export type Dictionary = typeof import('./zh.json')

const dictionaries: Record<Locale, () => Promise<Dictionary>> = {
  zh: () => import('./zh.json').then((m) => m.default),
  en: () => import('./en.json').then((m) => m.default),
}

export async function getDictionary(locale: Locale): Promise<Dictionary> {
  return dictionaries[locale]()
}
