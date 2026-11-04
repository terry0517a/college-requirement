import type { Dictionary } from '@/i18n/dictionaries'

export default function SiteFooter({ dict }: { dict: Dictionary }) {
  return (
    <footer className="border-t border-line text-sm text-subtle">
      <div className="mx-auto max-w-5xl px-4 py-4">{dict.site.name} · {dict.site.tagline}</div>
    </footer>
  )
}
