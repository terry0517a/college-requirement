// @vitest-environment node
import { getProgram, listProgramIdsForPrerender } from './program'

test('TW program: three latest years only, newest first', async () => {
  const p = (await getProgram(101))!
  expect(p.twDistribution.map((d) => d.year)).toEqual([2026, 2025, 2024])
  expect(p.twApply.map((a) => a.year)).toEqual([2026, 2025, 2024])
  expect(p.twApply[0].requirement.stage2?.items?.[0]).toMatchObject({ name: '審查資料', pct: 50 })
  expect(p.twSieve[0].steps[0]).toMatchObject({ order: 1, min_score: expect.any(Number) })
  expect(p.twSieve[0].tiebreak).toBe('同級分超額篩選')
  expect(p.twDistribution[0]).toMatchObject({ minScore: 62.75, admittedCount: 47 })
  expect(p.institution).toMatchObject({ id: 1, country: 'TW', webUrl: 'https://www.ntu.edu.tw/' })
  expect(p.program).toMatchObject({ id: 101, nameZh: '資訊工程學系', field: { code: 'cs' } })
  expect(p.us).toBeNull()
})
test('partial TW data', async () => {
  const h = (await getProgram(103))!
  expect(h.twApply).toHaveLength(1)
  expect(h.twSieve).toEqual([])
  expect(h.twDistribution).toEqual([])
  const a = (await getProgram(201))!
  expect([a.twApply, a.twSieve, a.twDistribution]).toEqual([[], [], []])
})
test('US CIP program uses school-level data', async () => {
  const p = (await getProgram(1002))!
  expect(p.us).toMatchObject({ isSchoolLevel: true, allProgramId: 1001 })
  expect(p.us!.years[0].admissionRate).toBe(0.0361)
  expect(p.us!.sources.length).toBeGreaterThan(0)
  expect(p.twApply).toEqual([])
})
test('US school-level program itself', async () => {
  const p = (await getProgram(1001))!
  expect(p.us).toMatchObject({ isSchoolLevel: true, allProgramId: 1001 })
})
test('missing program is null', async () => {
  expect(await getProgram(999999)).toBeNull()
})
test('prerender ids', async () => {
  const ids = await listProgramIdsForPrerender(2)
  expect(ids.length).toBeGreaterThanOrEqual(1)
  expect(ids.length).toBeLessThanOrEqual(2)
  expect(ids).toContain(101)
})
