#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"

if ! brew list postgresql@17 >/dev/null 2>&1; then
  brew install postgresql@17
fi
brew services start postgresql@17

until pg_isready -q; do sleep 1; done

if ! psql -lqt postgres | cut -d'|' -f1 | grep -qw collegedata_test; then
  createdb collegedata_test
fi
echo "OK: collegedata_test ready"
