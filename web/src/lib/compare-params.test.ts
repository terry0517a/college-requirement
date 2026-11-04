import { MAX_COMPARE, parseCompareIds } from './compare-params'

test('parseCompareIds', () => {
  expect(parseCompareIds('101,abc,101,0,1001,102,103,1101')).toEqual([101, 1001, 102, 103])
  expect(parseCompareIds(undefined)).toEqual([])
  expect(parseCompareIds(['5,6', '7'])).toEqual([5, 6])
  expect(MAX_COMPARE).toBe(4)
})
