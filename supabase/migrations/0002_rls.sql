-- Row level security: the public site reads with the anon key; only the
-- pipeline (table owner via DATABASE_URL) writes. fetch_log stays private.

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then
    create role anon nologin;
  end if;
end
$$;

alter table source enable row level security;
alter table institution enable row level security;
alter table program enable row level security;
alter table admission_stat enable row level security;
alter table admission_requirement enable row level security;
alter table cost enable row level security;
alter table strength enable row level security;
alter table fetch_log enable row level security;

create policy "source_anon_read" on source for select to anon using (true);
create policy "institution_anon_read" on institution for select to anon using (true);
create policy "program_anon_read" on program for select to anon using (true);
create policy "admission_stat_anon_read" on admission_stat for select to anon using (true);
create policy "admission_requirement_anon_read" on admission_requirement for select to anon using (true);
create policy "cost_anon_read" on cost for select to anon using (true);
create policy "strength_anon_read" on strength for select to anon using (true);

create unique index institution_openalex_id_key on institution (openalex_id) where openalex_id is not null;
