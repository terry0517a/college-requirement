-- Read-only role the Next.js website logs in as. It inherits anon so the
-- *_anon_read RLS policies (0002, 0003) apply, and gets select only on the
-- public data tables. fetch_log and cac_fetch stay private.
-- Production: the owner sets a password and LOGIN on this role in Supabase
-- (see plan 3a, Task 10). The role itself is created nologin here.
--
-- Privacy note: on plain Postgres the missing grants protect fetch_log and
-- cac_fetch (permission error). On Supabase, anon usually already has default
-- table privileges, which web_reader inherits; there RLS (enabled with no anon
-- policy in 0002/0005) is the protection, so those tables read as 0 rows, and
-- writes are blocked only because no write policy exists. Every new table must
-- enable RLS (pinned by test_every_public_table_has_rls).

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'web_reader') then
    create role web_reader nologin;
  end if;
end
$$;

grant anon to web_reader;
grant usage on schema public to web_reader;
grant select on source, institution, program, admission_stat, admission_requirement,
  cost, strength, field, institution_stat to web_reader;
