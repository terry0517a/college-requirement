# College Requirement

University-information website. `pipeline/` is a Python pipeline that loads public admission data into PostgreSQL.

## Local setup

1. `scripts/setup-local-db.sh` installs and starts PostgreSQL 17 and creates `collegedata_test`.
2. postgresql@17 is keg-only; add it to your shell PATH:
   `export PATH="/opt/homebrew/opt/postgresql@17/bin:$PATH"`
3. `cd pipeline && uv python install 3.12 && uv sync`
4. Copy `pipeline/.env.example` to `pipeline/.env`.
5. `uv run pytest`

Env vars: `DATABASE_URL` (production), `TEST_DATABASE_URL` (default `postgresql://localhost/collegedata_test`).
