import type { Dictionary } from '@/i18n/dictionaries'
import type { ProgramDetail } from '@/lib/queries/program'

const th = 'px-3 py-2 text-left font-medium whitespace-nowrap'
const td = 'px-3 py-2 align-top whitespace-nowrap'

/** Year x screening step: each cell shows the step label and its minimum grade. */
export default function SieveTable({ rows, dict }: { rows: ProgramDetail['twSieve']; dict: Dictionary }) {
  const t = dict.program
  const maxSteps = Math.max(...rows.map((r) => Math.max(...r.steps.map((s) => s.order), 0)), 0)
  const orders = Array.from({ length: maxSteps }, (_, i) => i + 1)
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line">
            <th className={th}>{t.year}</th>
            {orders.map((o) => (
              <th key={o} className={th}>
                {t.step} {o}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.year} className="border-b border-line">
              <td className={td}>
                {r.year}
                {r.tiebreak && <div className="text-xs text-subtle">{t.tiebreakNote}</div>}
              </td>
              {orders.map((o) => {
                const s = r.steps.find((x) => x.order === o)
                return (
                  <td key={o} className={td}>
                    {s ? (
                      <>
                        <div>{s.label}</div>
                        <div className="text-xs text-subtle">
                          {t.minScore} {s.min_score}
                        </div>
                      </>
                    ) : (
                      '—'
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
