import pytest, psycopg

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
