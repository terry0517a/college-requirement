import { parseExploreParams, toQueryString } from './explore-params'

const F = ['cs', 'business']
test('clamps and whitelists', () => {
  expect(parseExploreParams({ page: '-1', region: 'jp', field: 'xyz', control: 'state' }, F))
    .toMatchObject({ page: 1, region: 'all', field: null, control: null })
  expect(parseExploreParams({ page: '99999' }, F).page).toBe(500)
  expect(parseExploreParams({ page: '2.5' }, F).page).toBe(1)
  expect(parseExploreParams({ q: 'x'.repeat(300) }, F).q).toHaveLength(100)
  expect(parseExploreParams({ q: '   ' }, F).q).toBeNull()
  expect(parseExploreParams({ q: ['a', 'b'] }, F).q).toBe('a')
  expect(parseExploreParams({ maxTuition: '-5' }, F).maxTuition).toBeNull()
})
test('accepts valid values', () => {
  expect(
    parseExploreParams(
      { region: 'us', field: 'cs', control: 'public', maxTuition: '40000', size: 'large', page: '3' },
      F,
    ),
  ).toEqual({ q: null, region: 'us', field: 'cs', control: 'public', maxTuition: 40000, size: 'large', page: 3 })
  expect(parseExploreParams({ maxTuition: '1.5', size: 'huge' }, F)).toMatchObject({ maxTuition: null, size: null })
})
test('toQueryString omits defaults', () => {
  expect(toQueryString(parseExploreParams({}, F))).toBe('')
  expect(toQueryString(parseExploreParams({ region: 'us' }, F), { page: 2 })).toBe('region=us&page=2')
  expect(toQueryString(parseExploreParams({ q: 'a b&c' }, F))).toBe('q=a+b%26c')
})
