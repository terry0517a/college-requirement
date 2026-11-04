// @vitest-environment node
import { getCompareItems, type CompareItem } from './compare'

const series = (a: CompareItem['admission']) => a?.series ?? []

test('compare items keep order and skip missing', async () => {
  const items = await getCompareItems([1002, 999999, 101])
  expect(items.map((i) => i.programId)).toEqual([1002, 101])
  expect(items[0].requirementSummary).toMatchObject({ kind: 'us_sat', year: 2024, satTotal: { p25: 1510, p75: 1580 } })
  expect(items[1].admission).toMatchObject({ kind: 'tw_distribution' })
  expect(series(items[1].admission).map((s) => s.year)).toEqual([2026, 2025, 2024])
})
test('US item uses school-level data, has tuition, strengths and url-bearing sources', async () => {
  const [us, tw] = await getCompareItems([1002, 101])
  expect(us.institution).toMatchObject({ id: 10, country: 'US' })
  expect(us.admission).toMatchObject({ kind: 'us_rate' })
  expect(series(us.admission)[0]).toEqual({ year: 2024, rate: 0.0361 })
  expect(us.tuition).not.toBeNull()
  expect(us.sources.length).toBeGreaterThan(0)
  for (const s of [...us.sources, ...tw.sources]) expect(s).toEqual({ name: expect.any(String), url: expect.any(String), fetchedAt: expect.any(String) })
  expect(new Set(tw.sources.map((s) => `${s.name}\n${s.url}`)).size).toBe(tw.sources.length)
  expect(tw.topStrengthFields.length).toBeLessThanOrEqual(3)
  expect(tw.requirementSummary).toMatchObject({ kind: 'tw_apply', year: 2026 })
})
test('empty input', async () => {
  expect(await getCompareItems([])).toEqual([])
})
