import { hasLocale } from './config'

test('hasLocale accepts supported locales only', () => {
  expect(hasLocale('zh')).toBe(true)
  expect(hasLocale('en')).toBe(true)
  expect(hasLocale('jp')).toBe(false)
  expect(hasLocale('')).toBe(false)
})
