create table source (
  id serial primary key,
  code text unique not null,
  name text not null,
  url text not null,
  license text
);

create table institution (
  id serial primary key,
  country_code char(2) not null,
  name_en text not null,
  name_zh text,
  domain text not null,
  web_url text,
  openalex_id text,
  ror_id text,
  control text check (control in ('public','private')),
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (country_code, domain)
);
create index institution_country_code_idx on institution (country_code);

create table program (
  id serial primary key,
  institution_id int not null references institution,
  name_zh text,
  name_en text,
  field_code text,
  level text not null default 'bachelor',
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (institution_id, name_zh)
);
create index program_institution_id_idx on program (institution_id);

create table admission_stat (
  id serial primary key,
  program_id int not null references program,
  year int not null,
  pathway text not null,
  min_score numeric(7,2),
  admitted_count int not null,
  subjects jsonb not null default '[]',
  tiebreak text,
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (program_id, year, pathway)
);
create index admission_stat_program_id_year_idx on admission_stat (program_id, year);

create table admission_requirement (
  id serial primary key,
  program_id int not null references program,
  year int not null,
  pathway text not null,
  system_code text not null,
  requirement jsonb not null,
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (program_id, year, pathway)
);

create table cost (
  id serial primary key,
  institution_id int not null references institution,
  year int not null,
  residency text not null check (residency in ('local','out_of_state','international')),
  tuition numeric(12,2) not null,
  currency char(3) not null,
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (institution_id, year, residency)
);

create table strength (
  id serial primary key,
  institution_id int not null references institution,
  topic_id text not null,
  topic_name text not null,
  field_name text not null,
  works_count int not null,
  cited_by_count int not null,
  rank int not null,
  source_id int not null references source,
  source_url text not null,
  fetched_at timestamptz not null,
  unique (institution_id, topic_id)
);

create table fetch_log (
  id serial primary key,
  job text not null,
  started_at timestamptz not null,
  finished_at timestamptz,
  status text not null check (status in ('running','success','failed')),
  rows_written int,
  error text
);
create index fetch_log_job_started_at_idx on fetch_log (job, started_at desc);
