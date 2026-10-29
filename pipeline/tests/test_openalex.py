import json, pathlib, re, httpx
from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.openalex import OpenAlexJob
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
NTU = json.loads((FIXDIR / "openalex_ntu.json").read_text())
HIPO = [r for r in json.loads((FIXDIR / "hipo_sample.json").read_text()) if r["domains"][0] == "ntu.edu.tw"]

def test_writes_top10_strengths_and_ids(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=re.compile(r"https://api\.openalex\.org/institutions\?.*"), json=NTU)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 10
    assert db.execute("select openalex_id from institution").fetchone()[0] == NTU["results"][0]["id"]
    ranks = [x[0] for x in db.execute("select rank from strength order by rank").fetchall()]
    assert ranks == list(range(1, 11))

def test_skips_low_works_match(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    low = json.loads(json.dumps(NTU)); low["results"][0]["works_count"] = 5
    httpx_mock.add_response(url=re.compile(r"https://api\.openalex\.org/institutions\?.*"), json=low)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 0
    assert db.execute("select openalex_id from institution").fetchone()[0] is None

def test_query_includes_country_filter_and_key(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=re.compile(r"^(?=.*country_code(?::|%3A)TW)(?=.*api_key=k1).*$"), json=NTU)
    assert run_job(OpenAlexJob(client=httpx.Client(), api_key="k1"), db).status == "success"
