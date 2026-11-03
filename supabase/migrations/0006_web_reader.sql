-- Read-only role the Next.js website logs in as. It gets usage on the public
-- schema and select on the nine public data tables only, plus one explicit
-- `for select to web_reader using (true)` RLS policy per table. It does NOT
-- inherit anon (granting anon needs ADMIN OPTION on PG16+, which Supabase's
-- postgres role may lack). fetch_log and cac_fetch stay private.
-- Production: the owner sets a password and LOGIN on this role in Supabase
-- (see plan 3a, Task 10). The role itself is created nologin here.
--
-- Privacy holds by both missing grants and RLS on any platform: fetch_log and
-- cac_fetch have no grant (permission error on plain Postgres) and RLS enabled
-- with no web_reader policy (0 rows even where default privileges exist, as on
-- Supabase). Writes are impossible: no insert/update/delete grant and no write
-- policy. Every new table must enable RLS (pinned by test_every_public_table_has_rls).

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'web_reader') then
    create role web_reader nologin;
  end if;
  -- Earlier drafts of this migration granted anon; undo that where it was applied.
  if exists (select 1 from pg_auth_members m
             join pg_roles r on r.oid = m.roleid and r.rolname = 'anon'
             join pg_roles u on u.oid = m.member and u.rolname = 'web_reader') then
    revoke anon from web_reader;
  end if;
end
$$;

grant usage on schema public to web_reader;
grant select on source, institution, program, admission_stat, admission_requirement,
  cost, strength, field, institution_stat to web_reader;

drop policy if exists source_web_reader_read on source;
create policy source_web_reader_read on source for select to web_reader using (true);
drop policy if exists institution_web_reader_read on institution;
create policy institution_web_reader_read on institution for select to web_reader using (true);
drop policy if exists program_web_reader_read on program;
create policy program_web_reader_read on program for select to web_reader using (true);
drop policy if exists admission_stat_web_reader_read on admission_stat;
create policy admission_stat_web_reader_read on admission_stat for select to web_reader using (true);
drop policy if exists admission_requirement_web_reader_read on admission_requirement;
create policy admission_requirement_web_reader_read on admission_requirement for select to web_reader using (true);
drop policy if exists cost_web_reader_read on cost;
create policy cost_web_reader_read on cost for select to web_reader using (true);
drop policy if exists strength_web_reader_read on strength;
create policy strength_web_reader_read on strength for select to web_reader using (true);
drop policy if exists field_web_reader_read on field;
create policy field_web_reader_read on field for select to web_reader using (true);
drop policy if exists institution_stat_web_reader_read on institution_stat;
create policy institution_stat_web_reader_read on institution_stat for select to web_reader using (true);
