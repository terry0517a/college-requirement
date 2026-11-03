import Link from 'next/link'
import { getDictionary } from '@/i18n/dictionaries'

export default async function NotFound() {
  // not-found receives no params, so show both languages.
  const [zh, en] = await Promise.all([getDictionary('zh'), getDictionary('en')])
  return (
    <div className="space-y-2">
      <h1 className="text-2xl font-bold">{zh.notFound.title} / {en.notFound.title}</h1>
      <p>
        <Link href="/" className="text-brand hover:underline">
          {zh.notFound.back} / {en.notFound.back}
        </Link>
      </p>
    </div>
  )
}
