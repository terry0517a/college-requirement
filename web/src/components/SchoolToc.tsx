type Item = { id: string; label: string }

/** Anchor links: a fixed sidebar on desktop, a horizontally scrolling bar on phones. */
export default function SchoolToc({ items, label }: { items: Item[]; label: string }) {
  return (
    <nav
      aria-label={label}
      className="sticky top-0 z-10 -mx-4 overflow-x-auto border-b border-line bg-page px-4 py-2 lg:static lg:mx-0 lg:w-44 lg:shrink-0 lg:overflow-visible lg:border-0 lg:px-0 lg:py-0"
    >
      <ul className="flex gap-4 text-sm whitespace-nowrap lg:sticky lg:top-4 lg:flex-col lg:gap-2">
        {items.map((i) => (
          <li key={i.id}>
            <a href={`#${i.id}`} className="hover:text-brand">
              {i.label}
            </a>
          </li>
        ))}
      </ul>
    </nav>
  )
}
