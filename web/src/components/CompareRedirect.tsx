'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import { COMPARE_KEY, readList } from '@/lib/local-lists'

/** /compare without ?ids=: send visitors with a stored compare list to it. Renders nothing. */
export default function CompareRedirect({ locale }: { locale: string }) {
  const router = useRouter()
  useEffect(() => {
    const ids = readList(COMPARE_KEY)
    if (ids.length >= 1) router.replace(`/${locale}/compare?ids=${ids.join(',')}`)
  }, [locale, router])
  return null
}
