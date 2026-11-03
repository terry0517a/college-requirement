def test_db_fixture_connects(db):
    assert db.execute("select 1").fetchone() == (1,)
