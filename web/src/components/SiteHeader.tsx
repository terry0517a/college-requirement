import Link from 'next/link'
import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import LanguageSwitch from './LanguageSwitch'
import RegionSelect from './RegionSelect'

export default function SiteHeader({ locale, dict }: { locale: Locale; dict: Dictionary }) {
  return (
    <header className="border-b border-[var(--color-border)]">
      <div className="mx-auto flex max-w-5xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
        <Link href={`/${locale}`} className="font-semibold">
          {dict.site.name}
        </Link>
        <nav className="flex gap-4 text-sm">
          <Link href={`/${locale}/explore`} prefetch={false}>{dict.nav.explore}</Link>
          <Link href={`/${locale}/compare`} prefetch={false}>{dict.nav.compare}</Link>
          <Link href={`/${locale}/about`} prefetch={false}>{dict.nav.about}</Link>
        </nav>
        <div className="ml-auto flex items-center gap-4">
          <RegionSelect locale={locale} labels={dict.region} />
          <LanguageSwitch locale={locale} label={dict.lang.switchTo} />
        </div>
      </div>
    </header>
  )
}
