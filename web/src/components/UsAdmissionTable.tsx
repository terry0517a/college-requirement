import type { Locale } from '@/i18n/config'
import type { Dictionary } from '@/i18n/dictionaries'
import { formatPercent, formatRange } from '@/lib/format'
import type { UsAdmission } from '@/lib/queries/school'
import NoData from './NoData'
import SourceNote from './SourceNote'

const th = 'px-3 py-2 text-left font-medium whitespace-nowrap'
const td = 'px-3 py-2 whitespace-nowrap'

/** US school-level admission table (admission rate, SAT/ACT percentiles) plus one SourceNote per distinct source. */
export default function UsAdmissionTable({
  us,
  locale,
  dict,
  children,
}: {
  us: UsAdmission
  locale: Locale
  dict: Dictionary
  /** Extra content shown between the table and the source notes. */
  children?: React.ReactNode
}) {
  const t = dict.school
  const labels = { source: dict.common.source, fetched: dict.common.fetchedAt }
  const empty = us.years.length === 0 || us.years.every((y) => y.admissionRate === null && y.sat === null && y.act === null)
  const noTests = !empty && us.years.every((y) => y.sat === null && y.act === null)
  const sep = locale === 'zh' ? '：' : ': '
  return (
    <>
      {empty ? (
        <NoData label={dict.common.noData} />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <caption className="pb-1 text-left text-xs text-subtle">{t.percentileNote}</caption>
            <thead>
              <tr className="border-b border-line">
                <th className={th}>{t.year}</th>
                <th className={th}>{t.admissionRate}</th>
                <th className={th}>{t.satRw}</th>
                <th className={th}>{t.satMath}</th>
                <th className={th}>{t.satTotal}</th>
                <th className={th}>{t.act}</th>
              </tr>
            </thead>
            <tbody>
              {us.years.map((y) => (
                <tr key={y.year} className="border-b border-line">
                  <td className={td}>{y.year}</td>
                  <td className={td}>{formatPercent(y.admissionRate, locale)}</td>
                  <td className={td}>{formatRange(y.sat?.rw ?? null)}</td>
                  <td className={td}>{formatRange(y.sat?.math ?? null)}</td>
                  <td className={td}>{formatRange(y.sat?.total ?? null)}</td>
                  <td className={td}>{formatRange(y.act?.composite ?? null)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {noTests && (
        <NoData label={`${t.satTotal} / ${t.act}${sep}${dict.common.noData}`} />
      )}
      {children}
      {us.sources.map((x) => (
        <SourceNote key={`${x.name}-${x.url}`} name={x.name} url={x.url} fetchedAt={x.fetchedAt} locale={locale} labels={labels} />
      ))}
    </>
  )
}
