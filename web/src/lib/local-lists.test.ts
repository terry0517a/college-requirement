// @vitest-environment jsdom
import { readList, toggleInList, writeList } from './local-lists'

beforeEach(() => window.localStorage.clear())

test('toggle adds then removes and fires the change event', () => {
  const onChange = vi.fn()
  window.addEventListener('local-lists', onChange)
  expect(toggleInList('compare:v1', 5, 4)).toEqual({ ids: [5], added: true, full: false })
  expect(readList('compare:v1')).toEqual([5])
  expect(toggleInList('compare:v1', 5, 4)).toEqual({ ids: [], added: false, full: false })
  expect(onChange).toHaveBeenCalledTimes(2)
  window.removeEventListener('local-lists', onChange)
})
test('a full list refuses new ids but still allows removal', () => {
  writeList('compare:v1', [1, 2, 3, 4])
  expect(toggleInList('compare:v1', 9, 4)).toEqual({ ids: [1, 2, 3, 4], added: false, full: true })
  expect(readList('compare:v1')).toEqual([1, 2, 3, 4])
  expect(toggleInList('compare:v1', 2, 4).ids).toEqual([1, 3, 4])
})
test('no max means unbounded; junk in storage is ignored', () => {
  window.localStorage.setItem('favorites:v1', '[1,"x",2.5,3]')
  expect(readList('favorites:v1')).toEqual([1, 3])
  window.localStorage.setItem('favorites:v1', '{bad')
  expect(readList('favorites:v1')).toEqual([])
})
test('localStorage throwing yields [] and does not throw on write', () => {
  const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('denied')
  })
  const set = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('denied')
  })
  expect(readList('compare:v1')).toEqual([])
  expect(() => toggleInList('compare:v1', 1, 4)).not.toThrow()
  spy.mockRestore()
  set.mockRestore()
})
