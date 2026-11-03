// @vitest-environment node
import { getSchool, listSchoolIdsForPrerender, parseId } from './school'

test('parseId', () => {
  expect(parseId('1')).toBe(1)
  expect(parseId('abc')).toBeNull()
  expect(parseId('0')).toBeNull()
  expect(parseId('01')).toBeNull()
  expect(parseId('99999999999')).toBeNull()
  expect(parseId('2147483648')).toBeNull()
})
test('hidden or missing schools are null', async () => {
  expect(await getSchool(3)).toBeNull()
  expect(await getSchool(999999)).toBeNull()
})
test('TW school lists programs with data flags', async () => {
  const s = (await getSchool(1))!
  const by = Object.fromEntries(s.programs.map((p) => [p.nameZh, p]))
  expect(by['資訊工程學系']).toMatchObject({ hasApply: true, hasSieve: true, hasDistribution: true, field: { code: 'cs' } })
  expect(by['歷史學系']).toMatchObject({ hasApply: true, hasSieve: false, hasDistribution: false })
  expect(s.us).toBeNull()
  expect(s.costs).toEqual([])
})
test('US school: three latest years, costs, stat', async () => {
  const s = (await getSchool(10))!
  expect(s.us!.years.map((y) => y.year)).toEqual([2024, 2023, 2022])
  expect(s.us!.years[0]).toMatchObject({ admissionRate: 0.0361, sat: { total: { p25: 1510, p75: 1580 } } })
  expect(s.costs[0]).toMatchObject({ year: 2024, outOfState: 68544 })
  expect(s.stat).toMatchObject({ studentSize: 7554 })
  expect(s.programs[0].code).toBe('all')
})
test('school without scores has null sat/act', async () => {
  const s = (await getSchool(11))!
  expect(s.us!.years.every((y) => y.sat === null && y.act === null)).toBe(true)
})
test('strength ranks are site-relative', async () => {
  const ntu = (await getSchool(1))!
  const su = (await getSchool(10))!
  expect(ntu.strengths.fields.find((f) => f.name === 'Medicine')).toMatchObject({ rank: 1, of: 2 })
  expect(su.strengths.fields.find((f) => f.name === 'Computer Science')).toMatchObject({ rank: 1, of: 2 })
})
test('prerender ids: visible schools only, at least one', async () => {
  const ids = await listSchoolIdsForPrerender(5)
  expect(ids).toHaveLength(5)
  expect(ids).not.toContain(3)
  expect(ids.slice(0, 2)).toEqual([1, 10])
})
test('TW programs are in name order', async () => {
  const s = (await getSchool(1))!
  expect(s.programs.map((p) => p.nameZh)).toEqual(['歷史學系', '資訊工程學系', '醫學系'])
})
