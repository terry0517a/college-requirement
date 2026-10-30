-- US College Scorecard support: institution ids/location, program codes,
-- unified field taxonomy, admission rate, and institution-level stats.

alter table institution add column scorecard_id int;
alter table institution add column city text;
alter table institution add column region text;
create unique index institution_scorecard_id_key on institution (scorecard_id) where scorecard_id is not null;

alter table program add column code text;
create unique index program_institution_code_key on program (institution_id, code) where code is not null;

create table field (
  code text primary key,
  name_zh text not null,
  name_en text not null,
  sort int not null
);

insert into field (code, name_zh, name_en, sort) values
  ('cs', '資訊', 'Computer & Information Science', 1),
  ('engineering', '工程', 'Engineering', 2),
  ('math', '數學與統計', 'Mathematics & Statistics', 3),
  ('physical_science', '物理與化學', 'Physical Sciences', 4),
  ('life_science', '生命科學', 'Biological Sciences', 5),
  ('agriculture', '農業與環境', 'Agriculture & Natural Resources', 6),
  ('architecture', '建築與設計', 'Architecture & Design', 7),
  ('business', '商管', 'Business & Management', 8),
  ('social_science', '社會科學', 'Social Sciences', 9),
  ('public_affairs', '公共事務', 'Public Affairs & Services', 10),
  ('law', '法律', 'Law', 11),
  ('health', '醫學與健康', 'Medicine & Health', 12),
  ('psychology', '心理', 'Psychology', 13),
  ('education', '教育', 'Education', 14),
  ('humanities', '人文', 'Humanities', 15),
  ('arts', '藝術', 'Visual & Performing Arts', 16),
  ('communication', '傳播', 'Communication & Media', 17),
  ('interdisciplinary', '跨領域', 'Interdisciplinary', 18),
  ('applied', '技職與應用', 'Trades & Applied Studies', 19)
on conflict (code) do nothing;

alter table program add constraint program_field_code_fkey foreign key (field_code) references field (code);

alter table admission_stat add column admission_rate numeric(6,5);
alter table admission_stat alter column admitted_count drop not null;

create table institution_stat (
  id serial primary key,
  institution_id int not null references institution,
  year int not null,
  student_size int,
  completion_rate numeric(6,5),
  median_earnings numeric(12,2),
  currency char(3),
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (institution_id, year)
);

alter table field enable row level security;
alter table institution_stat enable row level security;

create policy "field_anon_read" on field for select to anon using (true);
create policy "institution_stat_anon_read" on institution_stat for select to anon using (true);
