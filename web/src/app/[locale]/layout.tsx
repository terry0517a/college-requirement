import type { Metadata } from 'next'
import { notFound } from 'next/navigation'
import { hasLocale, htmlLang, locales } from '@/i18n/config'
import { getDictionary } from '@/i18n/dictionaries'
import SiteHeader from '@/components/SiteHeader'
import SiteFooter from '@/components/SiteFooter'
import '../globals.css'

// SITE_URL (e.g. https://example.com) is also read by the sitemap.
export const metadata: Metadata = {
  metadataBase: new URL(process.env.SITE_URL ?? 'http://localhost:3000'),
  title: { default: '大學資訊整合 / University Finder', template: '%s | University Finder' },
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
      </body>
    </html>
  )
}
