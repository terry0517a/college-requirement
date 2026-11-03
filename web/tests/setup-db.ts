process.env.DATABASE_URL ??= 'postgresql://localhost/collegedata_web_test'

// Tests must never run against a dev or production database.
const dbName = new URL(process.env.DATABASE_URL).pathname.slice(1)
if (!dbName.endsWith('_test')) {
  throw new Error(`DATABASE_URL must point at a *_test database, got "${dbName}"`)
}
