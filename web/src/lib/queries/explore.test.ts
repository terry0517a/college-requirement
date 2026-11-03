// @vitest-environment node
import { parseExploreParams } from '../explore-params'
import { searchInstitutions } from './explore'

const FIELDS = ['cs', 'business', 'health', 'humanities', 'architecture', 'engineering']
const base = parseExploreParams({}, FIELDS)

test('hides institutions without programs and paginates', async () => {
  const r = await searchInstitutions(base, 'zh')
  expect(r.total).toBe(29)
  expect(r.items).toHaveLength(20)
  expect(r.items.map((i) => i.id)).not.toContain(3)
  const p2 = await searchInstitutions({ ...base, page: 2 }, 'zh')
  expect(p2.items).toHaveLength(9)
})
test('region, field, control filters', async () => {
  expect((await searchInstitutions({ ...base, region: 'us' }, 'zh')).total).toBe(2)
  const cs = await searchInstitutions({ ...base, field: 'cs' }, 'zh')
  expect(cs.items.map((i) => i.id).sort()).toEqual([1, 10])
  expect(cs.items.find((i) => i.id === 1)!.matchedPrograms.map((p) => p.nameZh)).toEqual(['資訊工程學系'])
  expect(
    (await searchInstitutions({ ...base, control: 'public', region: 'tw' }, 'zh')).items.map((i) => i.id),
  ).toEqual([1])
})
test('keyword matches program names and treats % and _ literally', async () => {
  expect((await searchInstitutions({ ...base, q: '資訊工程' }, 'zh')).items.map((i) => i.id)).toEqual([1])
  expect((await searchInstitutions({ ...base, q: 'stanford' }, 'en')).items.map((i) => i.id)).toEqual([10])
  expect((await searchInstitutions({ ...base, q: '%' }, 'zh')).total).toBe(0)
  expect((await searchInstitutions({ ...base, q: '_' }, 'zh')).total).toBe(0)
})
test('tuition and size filters use the latest year', async () => {
  expect((await searchInstitutions({ ...base, maxTuition: 40000 }, 'zh')).items.map((i) => i.id)).toEqual([11])
  expect((await searchInstitutions({ ...base, size: 'medium' }, 'zh')).items.map((i) => i.id)).toEqual([10])
  const s = (await searchInstitutions({ ...base, region: 'us' }, 'zh')).items.find((i) => i.id === 10)!
  expect(s.tuition).toMatchObject({ year: 2024, outOfState: 68544, currency: 'USD' })
  expect(s.tuition!.source.name).toBe('College Scorecard (U.S. Department of Education)')
  expect(s.tuition!.fetchedAt).toBe('2026-10-30T03:00:00.000Z')
})
test('english locale keeps Chinese-only names', async () => {
  const r = await searchInstitutions({ ...base, q: '資訊工程' }, 'en')
  expect(r.items[0].matchedPrograms[0]).toMatchObject({ nameZh: '資訊工程學系', nameEn: null })
})
test('items carry source and fetch time; no programs matched without q/field', async () => {
  const r = await searchInstitutions({ ...base, region: 'us' }, 'zh')
  const s = r.items.find((i) => i.id === 10)!
  expect(s.matchedPrograms).toEqual([])
  expect(s.programCount).toBe(3)
  expect(s.studentSize).toBe(7554)
  expect(s.source.name).toBe('College Scorecard (U.S. Department of Education)')
  expect(s.fetchedAt).toBe('2026-10-30T03:00:00.000Z')
})
