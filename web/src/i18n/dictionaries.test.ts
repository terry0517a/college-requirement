import zh from './zh.json'
import en from './en.json'

const keys = (o: object, p = ''): string[] =>
  Object.entries(o).flatMap(([k, v]) =>
    typeof v === 'object' && v !== null ? keys(v, `${p}${k}.`) : [`${p}${k}`],
  )

test('zh and en dictionaries have identical keys', () => {
  expect(keys(en).sort()).toEqual(keys(zh).sort())
})

test('no empty strings', () => {
  for (const d of [zh, en])
    for (const k of keys(d))
      expect(k.split('.').reduce((o: any, s) => o[s], d)).not.toBe('') // eslint-disable-line @typescript-eslint/no-explicit-any
})
