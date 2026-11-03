alter table institution add column openalex_checked_at timestamptz;
create index institution_openalex_checked_at_idx on institution (openalex_checked_at nulls first);
