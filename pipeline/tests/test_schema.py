import pytest, psycopg

def test_all_tables_exist(db):
    names = {r[0] for r in db.execute(
        "select table_name from information_schema.tables where table_schema='public'")}
    assert {"source","institution","program","admission_stat","admission_requirement",
            "cost","strength","fetch_log"} <= names

def test_institution_requires_source(db):
    with pytest.raises(psycopg.errors.NotNullViolation):
        db.execute("insert into institution(country_code,name_en,domain) values ('TW','X','x.edu.tw')")
