import type { Metadata } from 'next'
import { Suspense } from 'react'
import { notFound } from 'next/navigation'
import { hasLocale, htmlLang, locales } from '@/i18n/config'
import { getDictionary } from '@/i18n/dictionaries'
import SiteHeader from '@/components/SiteHeader'
import SiteFooter from '@/components/SiteFooter'
import CompareTray from '@/components/CompareTray'
import { SITE_URL } from '@/lib/site-url'
import '../globals.css'

export async function generateMetadata({ params }: LayoutProps<'/[locale]'>): Promise<Metadata> {
  const { locale } = await params
  if (!hasLocale(locale)) return {}
  const name = (await getDictionary(locale)).site.name
  return {
    metadataBase: new URL(SITE_URL),
    title: { default: name, template: `%s | ${name}` },
  }
}

export function generateStaticParams() {
  return locales.map((locale) => ({ locale }))
}

export default async function RootLayout({ children, params }: LayoutProps<'/[locale]'>) {
  const { locale } = await params
  if (!hasLocale(locale)) notFound()
  const dict = await getDictionary(locale)
  return (
    <html lang={htmlLang[locale]}>
      <body className="flex min-h-screen flex-col">
        <SiteHeader locale={locale} dict={dict} />
        <main className="mx-auto w-full max-w-5xl flex-1 px-4 py-8">{children}</main>
        <SiteFooter dict={dict} />
        <Suspense fallback={null}>
          <CompareTray locale={locale} labels={dict.compare} />
        </Suspense>
      </body>
    </html>
  )
}
