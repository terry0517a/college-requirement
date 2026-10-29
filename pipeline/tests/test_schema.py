import pytest, psycopg
from collegedata.sources import ensure_source

def test_all_tables_exist(db):
    names = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"source","institution","program","admission_stat","admission_requirement",
            "cost","strength","fetch_log"} <= names

def test_institution_requires_source(db):
    with pytest.raises(psycopg.errors.NotNullViolation):
        db.execute("insert into institution(country_code,name_en,domain) values ('TW','X','x.edu.tw')")

TABLES = ["source", "institution", "program", "admission_stat", "admission_requirement",
          "cost", "strength", "fetch_log"]

def test_rls_enabled_on_every_table(db):
    rows = dict(db.execute("select relname, relrowsecurity from pg_class where relname = any(%s) and relkind='r'",
                           (TABLES,)).fetchall())
    assert rows == {t: True for t in TABLES}

def test_anon_read_policies(db):
    pol = {r[0]: r[1:] for r in db.execute("select tablename, policyname, cmd, roles from pg_policies where schemaname='public'")}
    assert "fetch_log" not in pol
    for t in TABLES[:-1]:
        assert pol[t] == (f"{t}_anon_read", "SELECT", ["anon"])

def test_openalex_id_unique(db):
    sid = db.execute("insert into source(code,name,url) values('s','s','u') returning id").fetchone()[0]
    sql = """insert into institution(country_code,name_en,domain,openalex_id,source_id,source_url,fetched_at)
             values ('TW','X',%s,'https://openalex.org/I1',%s,'u',now())"""
    db.execute(sql, ("a.edu.tw", sid))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute(sql, ("b.edu.tw", sid))


def test_0003_columns_and_tables(db):
    names = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"field", "institution_stat"} <= names
    cols = {r[0] for r in db.execute(
        "select column_name from information_schema.columns where table_name='institution'")}
    assert {"scorecard_id", "city", "region"} <= cols
    assert db.execute("select count(*) from field").fetchone()[0] == 19
    assert db.execute("select is_nullable from information_schema.columns "
                      "where table_name='admission_stat' and column_name='admitted_count'").fetchone()[0] == "YES"

def test_program_code_unique_per_institution(db):
    sid = ensure_source(db, "hipo")
    iid = db.execute("insert into institution(country_code,name_en,domain,source_id,source_url,fetched_at) "
                     "values ('US','X','x.edu',%s,'u',now()) returning id", (sid,)).fetchone()[0]
    db.execute("insert into program(institution_id,code,name_en,source_id,source_url,fetched_at) values (%s,'11','CS',%s,'u',now())", (iid, sid))
    with pytest.raises(psycopg.errors.UniqueViolation):
        db.execute("insert into program(institution_id,code,name_en,source_id,source_url,fetched_at) values (%s,'11','CS',%s,'u',now())", (iid, sid))

def test_program_field_code_must_exist(db):
    sid = ensure_source(db, "hipo")
    iid = db.execute("insert into institution(country_code,name_en,domain,source_id,source_url,fetched_at) "
                     "values ('US','X','x.edu',%s,'u',now()) returning id", (sid,)).fetchone()[0]
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        db.execute("insert into program(institution_id,code,field_code,source_id,source_url,fetched_at) values (%s,'99','nope',%s,'u',now())", (iid, sid))
