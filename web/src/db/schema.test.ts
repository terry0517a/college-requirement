// @vitest-environment node
import { is } from 'drizzle-orm'
import { getTableConfig, PgTable } from 'drizzle-orm/pg-core'
import { sql } from './client'
import * as schema from './schema'

const tables = Object.values(schema).filter((v) => is(v, PgTable)) as PgTable[]

test('schema covers the expected tables', () => {
  expect(tables.map((t) => getTableConfig(t).name).sort()).toEqual([
    'admission_requirement',
    'admission_stat',
    'cost',
    'field',
    'institution',
    'institution_stat',
    'program',
    'source',
    'strength',
  ])
})

test.each(tables.map((t) => [getTableConfig(t).name, t] as const))(
  'every column of %s exists in the database',
  async (name, table) => {
    const rows = await sql<{ column_name: string }[]>`
      select column_name from information_schema.columns
      where table_schema = 'public' and table_name = ${name}`
    const dbColumns = new Set(rows.map((r) => r.column_name))
    for (const col of getTableConfig(table).columns) {
      expect(dbColumns, `${name}.${col.name}`).toContain(col.name)
    }
  },
)

afterAll(async () => {
  await sql.end()
})
