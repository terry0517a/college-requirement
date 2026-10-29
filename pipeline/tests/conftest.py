import os
from pathlib import Path

import psycopg
import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "supabase" / "migrations"
DEFAULT_TEST_URL = "postgresql://localhost/collegedata_test"


@pytest.fixture(scope="session")
def test_database_url():
    url = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_URL)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("drop schema public cascade; create schema public;")
        for sql_file in sorted(MIGRATIONS_DIR.glob("*.sql")):
            conn.execute(sql_file.read_text(encoding="utf-8"))
    return url


@pytest.fixture
def db(test_database_url):
    conn = psycopg.connect(test_database_url, autocommit=False)
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
