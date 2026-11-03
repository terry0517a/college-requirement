import { notFound } from 'next/navigation'

// Catches every unmatched URL under a locale so it renders [locale]/not-found.tsx with a real 404.
export default function CatchAll() {
  notFound()
}
