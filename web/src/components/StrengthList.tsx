import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import type { SchoolDetail } from '@/lib/queries/school'
import NoData from './NoData'

export default function StrengthList({
  strengths,
  locale,
  dict,
}: {
  strengths: SchoolDetail['strengths']
  locale: Locale
  dict: Dictionary
}) {
  if (strengths.fields.length === 0) return <NoData label={dict.common.noData} />
  const t = dict.school
  const num = (n: number) => n.toLocaleString(locale === 'zh' ? 'zh-TW' : 'en-US')
  return (
    <div className="space-y-4">
      <ul className="space-y-2">
        {strengths.fields.map((f) => (
          <li key={f.name} className="flex flex-wrap items-baseline gap-x-3 text-sm">
            <span className="font-medium break-words">{f.name}</span>
            <span className="text-subtle">
              {t.works} {num(f.works)}
            </span>
            <span className="text-subtle">{t.siteRank.replace('{rank}', String(f.rank)).replace('{of}', String(f.of))}</span>
          </li>
        ))}
      </ul>
      {strengths.topics.length > 0 && (
        <div>
          <h3 className="text-sm font-semibold">{t.topTopics}</h3>
          <ol className="mt-1 list-inside list-decimal space-y-1 text-sm">
            {strengths.topics.map((x) => (
              <li key={`${x.field}-${x.name}`} className="break-words">
                {x.name} <span className="text-subtle">({x.field} · {num(x.works)})</span>
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}
