def test_db_fixture_connects(db):
    assert db.execute("select 1").fetchone() == (1,)


def test_cli_knows_cac_jobs():
    from collegedata.runner import REGISTRY
    assert {"cac_sieve", "cac_rules"} <= set(REGISTRY)
