import json, pathlib, re, httpx
from collegedata.jobs.hipo import HipoJob, upsert_institutions
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIX = json.loads(pathlib.Path(__file__).with_name("fixtures").joinpath("hipo_sample.json").read_text())

def test_upsert_is_idempotent(db):
    sid = ensure_source(db, "hipo")
    assert upsert_institutions(db, FIX, sid, "http://x") == 3
    assert upsert_institutions(db, FIX, sid, "http://x") == 3
    assert db.execute("select count(*) from institution").fetchone()[0] == 3

def test_country_and_domain_mapping(db):
    sid = ensure_source(db, "hipo")
    upsert_institutions(db, FIX, sid, "http://x")
    row = db.execute("select country_code, name_en, domain, web_url from institution where domain='ntu.edu.tw'").fetchone()
    assert row == ("TW", "National Taiwan University", "ntu.edu.tw", "http://www.ntu.edu.tw/")

def test_job_fetches_each_supported_country(db, httpx_mock):
    httpx_mock.add_response(url=re.compile(r"http://universities\.hipolabs\.com/search\?country=Taiwan.*"), json=[r for r in FIX if r["alpha_two_code"]=="TW"])
    httpx_mock.add_response(url=re.compile(r"http://universities\.hipolabs\.com/search\?country=United.*"), json=[r for r in FIX if r["alpha_two_code"]=="US"])
    assert run_job(HipoJob(client=httpx.Client()), db).rows_written == 3

def test_does_not_overwrite_rows_owned_by_other_sources(db):
    hipo = ensure_source(db, "hipo"); sc = ensure_source(db, "scorecard")
    upsert_institutions(db, FIX, hipo, "http://x")
    db.execute("update institution set name_en='Stanford University', source_id=%s, scorecard_id=243744 where domain='stanford.edu'", (sc,))
    assert upsert_institutions(db, FIX, hipo, "http://y") == 3
    row = db.execute("select name_en, source_id, source_url from institution where domain='stanford.edu'").fetchone()
    assert row == ("Stanford University", sc, "http://x")
    assert db.execute("select source_url from institution where domain='ntu.edu.tw'").fetchone()[0] == "http://y"
