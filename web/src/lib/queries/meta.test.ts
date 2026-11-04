// @vitest-environment node
import { listFields, listSources } from './meta'

test('listFields returns the 19 fields in sort order', async () => {
  const fields = await listFields()
  expect(fields).toHaveLength(19)
  expect(fields[0]).toMatchObject({ code: 'cs', sort: 1 })
  expect(fields.map((f) => f.sort)).toEqual([...fields.map((f) => f.sort)].sort((a, b) => a - b))
})

test('listSources includes scorecard', async () => {
  const sources = await listSources()
  expect(sources.map((s) => s.code)).toContain('scorecard')
  expect(sources.find((s) => s.code === 'scorecard')).toMatchObject({
    url: 'https://collegescorecard.ed.gov/',
  })
})
