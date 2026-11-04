import { displayName } from './names'

test('zh prefers Chinese, falls back to English', () => {
  expect(displayName('zh', '臺灣大學', 'NTU')).toBe('臺灣大學')
  expect(displayName('zh', null, 'Stanford')).toBe('Stanford')
})

test('en prefers English, falls back to Chinese', () => {
  expect(displayName('en', '臺灣大學', 'NTU')).toBe('NTU')
  expect(displayName('en', '資訊工程學系', null)).toBe('資訊工程學系')
})

test('both missing gives a dash', () => {
  expect(displayName('zh', null, null)).toBe('—')
  expect(displayName('en', null, null)).toBe('—')
})
