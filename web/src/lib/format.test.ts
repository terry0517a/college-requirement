import { formatDate, formatMoney, formatPercent, formatRange } from './format'

test('formatDate renders YYYY-MM-DD in Asia/Taipei', () => {
  expect(formatDate(new Date('2026-10-30T03:00:00Z'), 'zh')).toBe('2026-10-30')
  // 17:00 UTC is already the next day in Taipei (UTC+8)
  expect(formatDate(new Date('2026-10-30T17:00:00Z'), 'en')).toBe('2026-10-31')
  expect(formatDate('2026-10-30T03:00:00Z', 'en')).toBe('2026-10-30')
})

test('formatMoney', () => {
  expect(formatMoney(null, 'USD', 'zh')).toBe('—')
  expect(formatMoney(68544, 'USD', 'en')).toBe('$68,544')
  expect(formatMoney(12000, 'USD', 'zh')).toContain('12,000')
})

test('formatPercent', () => {
  expect(formatPercent(0.0361, 'en')).toBe('3.6%')
  expect(formatPercent(0.9164, 'zh')).toBe('91.6%')
  expect(formatPercent(null, 'zh')).toBe('—')
})

test('formatRange', () => {
  expect(formatRange({ p25: 740, p75: 780 })).toBe('740–780')
  expect(formatRange(null)).toBe('—')
})
