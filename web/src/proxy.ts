import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'
import { defaultLocale, hasLocale } from '@/i18n/config'

function pickLocale(req: NextRequest): string {
  const header = req.headers.get('accept-language') ?? ''
  for (const part of header.split(',')) {
    const base = part.split(';')[0].trim().toLowerCase().split('-')[0]
    if (hasLocale(base)) return base
  }
  return defaultLocale
}

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl
  const prefixed = pathname.split('/')[1]
  if (hasLocale(prefixed)) return
  request.nextUrl.pathname = `/${pickLocale(request)}${pathname === '/' ? '' : pathname}`
  return NextResponse.redirect(request.nextUrl, 307)
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|.*\\..*).*)'],
}
