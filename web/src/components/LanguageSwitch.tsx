'use client'

import { Suspense } from 'react'
import Link from 'next/link'
import { usePathname, useSearchParams } from 'next/navigation'
import { hasLocale, type Locale } from '@/i18n/config'

function Inner({ locale, label }: { locale: Locale; label: string }) {
  const pathname = usePathname()
  const search = useSearchParams().toString()
  const other: Locale = locale === 'zh' ? 'en' : 'zh'
  const segments = pathname.split('/')
  if (hasLocale(segments[1])) segments[1] = other
  else segments.splice(1, 0, other)
  const href = segments.join('/') + (search ? `?${search}` : '')
  return (
    <Link href={href} prefetch={false} hrefLang={other} className="text-sm text-[var(--color-accent)] hover:underline">
      {label}
    </Link>
  )
}

export default function LanguageSwitch(props: { locale: Locale; label: string }) {
  return (
    <Suspense fallback={<span className="text-sm text-[var(--color-muted)]">{props.label}</span>}>
      <Inner {...props} />
    </Suspense>
  )
}
