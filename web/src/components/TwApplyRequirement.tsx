import type { TwApplyRequirement as Requirement } from '@/db/types'
import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'

const sep = (locale: Locale) => (locale === 'zh' ? '、' : ', ')

/** One year's CAC requirement: quota, standards, multipliers, extras and the stage 2 schedule. */
export default function TwApplyRequirement({
  requirement: r,
  locale,
  dict,
}: {
  requirement: Requirement
  locale: Locale
  dict: Dictionary
}) {
  const t = dict.program
  const thresholds = Object.entries(r.thresholds ?? {}).filter(([, v]) => v !== null && v !== '')
  const multipliers = Object.entries(r.multipliers ?? {}).filter(([, v]) => v !== null)
  const extra = Object.entries(r.extra ?? {})
  const s2 = r.stage2
  const weights = Object.entries(s2?.gsat_weights ?? {}).filter(([, v]) => v !== null)
  const row = (label: string, value: React.ReactNode) => (
    <>
      <dt className="text-subtle">{label}</dt>
      <dd className="break-words">{value}</dd>
    </>
  )
  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
        {row(t.cacCode, r.cac_code)}
        {r.group && row(t.group, r.group)}
        {r.gender && row(t.gender, r.gender)}
        {r.quota !== null && row(t.quota, r.quota)}
        {thresholds.length > 0 && row(t.thresholds, thresholds.map(([k, v]) => `${k} ${v}`).join(sep(locale)))}
        {multipliers.length > 0 && row(t.multipliers, multipliers.map(([k, v]) => `${k} ×${v}`).join(sep(locale)))}
        {extra.length > 0 && row(t.extra, extra.map(([k, v]) => `${k} ${v}`).join(sep(locale)))}
      </dl>
      {s2 ? (
        <div className="space-y-2">
          <h4 className="font-medium">{t.stage2}</h4>
          <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
            {weights.length > 0 && row(t.gsatWeights, weights.map(([k, v]) => `${k} ×${v}`).join(sep(locale)))}
            {s2.stage1_pct != null && row(t.stage1Pct, `${s2.stage1_pct}%`)}
            {s2.tiebreak_order && s2.tiebreak_order.length > 0 && row(t.tiebreakOrder, s2.tiebreak_order.join(' > '))}
            {s2.review_items && row(t.reviewItems, s2.review_items)}
            {s2.exam_date && row(t.examDate, s2.exam_date)}
            {s2.expected_candidates != null && row(t.expectedCandidates, s2.expected_candidates)}
            {s2.fee != null && row(t.fee, s2.fee.toLocaleString(locale === 'zh' ? 'zh-TW' : 'en-US'))}
            {s2.website &&
              row(
                t.website,
                <a href={s2.website} target="_blank" rel="noopener noreferrer" className="break-all text-brand underline">
                  {s2.website}
                </a>,
              )}
          </dl>
          {s2.items && s2.items.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <caption className="pb-1 text-left text-xs text-subtle">{t.items}</caption>
                <thead>
                  <tr className="border-b border-line">
                    <th className="px-3 py-2 text-left font-medium whitespace-nowrap">{t.itemName}</th>
                    <th className="px-3 py-2 text-left font-medium whitespace-nowrap">{t.itemThreshold}</th>
                    <th className="px-3 py-2 text-left font-medium whitespace-nowrap">{t.itemPct}</th>
                  </tr>
                </thead>
                <tbody>
                  {s2.items.map((it) => (
                    <tr key={it.name} className="border-b border-line">
                      <td className="px-3 py-2">{it.name}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{it.threshold ?? '—'}</td>
                      <td className="px-3 py-2 whitespace-nowrap">{it.pct != null ? `${it.pct}%` : '—'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : (
        <p className="text-xs text-subtle">{t.stage1Only}</p>
      )}
      {(r.sources?.sieve_image || r.sources?.rules_page) && (
        <ul className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          {r.sources.sieve_image && (
            <li>
              <a href={r.sources.sieve_image} target="_blank" rel="noopener noreferrer" className="text-brand underline">
                {t.sieveImage}
              </a>
            </li>
          )}
          {r.sources.rules_page && (
            <li>
              <a href={r.sources.rules_page} target="_blank" rel="noopener noreferrer" className="text-brand underline">
                {t.rulesPage}
              </a>
            </li>
          )}
        </ul>
      )}
    </div>
  )
}
