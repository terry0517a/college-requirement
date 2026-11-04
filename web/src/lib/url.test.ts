import { safeHttpUrl } from './url'

test('accepts http and https only', () => {
  expect(safeHttpUrl('https://a.example/x')).toBe('https://a.example/x')
  expect(safeHttpUrl(' http://a.example ')).toBe('http://a.example')
  for (const bad of ['javascript:alert(1)', ' JAVASCRIPT:x', 'data:text/html,x', '/x', '', '   ', null, undefined, 5, {}]) {
    expect(safeHttpUrl(bad)).toBeNull()
  }
})
