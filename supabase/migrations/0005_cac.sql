-- CAC (大學甄選入學委員會) scraping: per-school sieve data and fetch progress.

alter table admission_stat add column sieve jsonb;

create table cac_fetch (
  id bigint generated always as identity primary key,
  job text not null,
  roc_year int not null,
  school_code char(3) not null,
  url text not null,
  status text not null check (status in ('done', 'failed')),
  rows_written int,
  rows_skipped int,
  error text,
  attempts int not null default 0,  -- every outcome (done or failed) adds 1
  fetched_at timestamptz not null,
  unique (job, roc_year, school_code)
);

-- Private like fetch_log: RLS on, no anon policy.
alter table cac_fetch enable row level security;
