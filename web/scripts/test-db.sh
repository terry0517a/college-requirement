#!/usr/bin/env bash
# Recreate the web test database from the pipeline migrations plus the seed fixture.
# Connection comes from the usual PG* env vars (PGHOST, PGUSER, PGPASSWORD, PGPORT);
# PGHOST defaults to localhost for local development.
set -euo pipefail

DB_NAME="${WEB_TEST_DB:-collegedata_web_test}"
if [[ "$DB_NAME" != *_test ]]; then
  echo "refusing to run: database name '$DB_NAME' does not end with _test" >&2
  exit 1
fi

export PGHOST="${PGHOST:-localhost}"
if ! command -v psql >/dev/null 2>&1 && [ -d /opt/homebrew/opt/postgresql@17/bin ]; then
  export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"
fi

export PGOPTIONS="${PGOPTIONS:-} -c client_min_messages=warning"

cd "$(dirname "$0")/.."

dropdb --if-exists "$DB_NAME"
createdb "$DB_NAME"
for f in ../supabase/migrations/*.sql; do
  psql -q -v ON_ERROR_STOP=1 -d "$DB_NAME" -f "$f" >/dev/null
done
psql -q -v ON_ERROR_STOP=1 -d "$DB_NAME" -f tests/fixtures/seed.sql >/dev/null
echo "$DB_NAME ready"
