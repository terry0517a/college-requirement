import 'server-only'
import { drizzle, type PostgresJsDatabase } from 'drizzle-orm/postgres-js'
import postgres, { type Sql } from 'postgres'
import * as schema from './schema'

type Clients = { sql: Sql; db: PostgresJsDatabase<typeof schema> }
let clients: Clients | undefined

// Created on first use so a missing DATABASE_URL fails with a clear message at
// the first query, not at import time (e.g. during `next build` of static pages).
function get(): Clients {
  if (!clients) {
    const url = process.env.DATABASE_URL
    if (!url) throw new Error('DATABASE_URL is not set')
    // prepare: false because Supabase's transaction pooler has no prepared statements.
    const sql = postgres(url, { prepare: false, max: 5, idle_timeout: 20 })
    clients = { sql, db: drizzle(sql, { schema }) }
  }
  return clients
}

function lazy<T extends object>(pick: (c: Clients) => T): T {
  return new Proxy((() => {}) as unknown as T, {
    apply: (_t, thisArg, args) => Reflect.apply(pick(get()) as never, thisArg, args),
    get(_t, prop) {
      const target = pick(get())
      const value = Reflect.get(target, prop)
      return typeof value === 'function' ? value.bind(target) : value
    },
  })
}

export const sql: Sql = lazy((c) => c.sql)
export const db: PostgresJsDatabase<typeof schema> = lazy((c) => c.db)
