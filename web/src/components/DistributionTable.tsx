import type { Dictionary } from '@/i18n/dictionaries'
import type { ProgramDetail } from '@/lib/queries/program'

const th = 'px-3 py-2 text-left font-medium whitespace-nowrap'
const td = 'px-3 py-2 align-top'

/** UAC placement history: year, lowest admitted score, admitted count, scored subjects with weights. */
export default function DistributionTable({ rows, dict }: { rows: ProgramDetail['twDistribution']; dict: Dictionary }) {
  const t = dict.program
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            <th className={th}>{t.year}</th>
            <th className={th}>{t.minAdmitScore}</th>
            <th className={th}>{t.admittedCount}</th>
            <th className={th}>{t.subjects}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.year} className="border-b border-line">
              <td className={`${td} whitespace-nowrap`}>{r.year}</td>
              <td className={`${td} whitespace-nowrap`}>{r.minScore ?? '—'}</td>
              <td className={`${td} whitespace-nowrap`}>{r.admittedCount ?? '—'}</td>
              <td className={`${td} min-w-48`}>
                {r.subjects.length ? r.subjects.map((s) => `${s.subject} ×${s.weight}`).join('、') : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
