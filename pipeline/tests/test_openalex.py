import json, pathlib, re, httpx
from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.openalex import OpenAlexJob
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
NTU = json.loads((FIXDIR / "openalex_ntu.json").read_text())
HIPO = [r for r in json.loads((FIXDIR / "hipo_sample.json").read_text()) if r["domains"][0] == "ntu.edu.tw"]
FIX_ALL = json.loads((FIXDIR / "hipo_sample.json").read_text())

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
    urls = [x[0] for x in db.execute("select source_url from strength").fetchall()]
    assert urls and all("api_key" not in u and "search=" in u and "country_code" in u for u in urls)

URL_RE = re.compile(r"https://api\.openalex\.org/institutions\?.*")
OLD = {"name": "National Taiwan University (old)", "web_pages": ["http://old.ntu.tw/"],
       "alpha_two_code": "TW", "domains": ["old.ntu.tw"], "country": "Taiwan, Province of China"}

def _ntu_id(db):
    return db.execute("select id from institution where domain='ntu.edu.tw'").fetchone()[0]

def test_rerun_is_idempotent(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, json=NTU, is_reusable=True)
    assert run_job(OpenAlexJob(client=httpx.Client()), db).status == "success"
    assert run_job(OpenAlexJob(client=httpx.Client()), db).status == "success"
    ranks = [x[0] for x in db.execute("select rank from strength where institution_id=%s order by rank", (_ntu_id(db),))]
    assert ranks == list(range(1, 11))

def test_refresh_removes_stale_topics(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    db.execute("""insert into strength (institution_id, topic_id, topic_name, field_name, works_count, cited_by_count,
                  rank, source_id, source_url, fetched_at)
                  values (%s, 'https://openalex.org/T0', 'Bogus', 'Bogus', 1, 0, 11, %s, 'http://x', now())""",
               (_ntu_id(db), ensure_source(db, "openalex")))
    httpx_mock.add_response(url=URL_RE, json=NTU)
    assert run_job(OpenAlexJob(client=httpx.Client()), db).status == "success"
    assert db.execute("select count(*) from strength where topic_id='https://openalex.org/T0'").fetchone()[0] == 0
    assert db.execute("select count(*) from strength").fetchone()[0] == 10

def test_skips_openalex_id_owned_by_other_institution(db, httpx_mock):
    upsert_institutions(db, HIPO + [OLD], ensure_source(db, "hipo"), "http://x")
    db.execute("update institution set openalex_id=%s, openalex_checked_at=now() where domain='ntu.edu.tw'",
               (NTU["results"][0]["id"],))
    httpx_mock.add_response(url=URL_RE, json=NTU)
    r = run_job(OpenAlexJob(client=httpx.Client(), limit=1), db)  # only the never-checked one is selected
    assert r.status == "success" and r.rows_written == 0
    assert db.execute("select openalex_id from institution where domain='old.ntu.tw'").fetchone()[0] is None
    assert db.execute("select count(*) from strength").fetchone()[0] == 0

def test_rate_limit_stops_cleanly(db, httpx_mock):
    upsert_institutions(db, HIPO + [OLD], ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, status_code=429)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 0
    assert len(httpx_mock.get_requests()) == 1

def test_http_error_for_one_institution_continues(db, httpx_mock, monkeypatch):
    monkeypatch.setattr("collegedata.jobs.openalex.time.sleep", lambda s: None)
    upsert_institutions(db, HIPO + [OLD], ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, status_code=500)
    httpx_mock.add_response(url=URL_RE, json=NTU)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "success" and r.rows_written == 10

def test_batch_size_from_env(db, httpx_mock, monkeypatch):
    monkeypatch.setenv("OPENALEX_BATCH_SIZE", "1")
    upsert_institutions(db, HIPO + [OLD], ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, json=NTU)
    assert run_job(OpenAlexJob(client=httpx.Client()), db).status == "success"
    assert len(httpx_mock.get_requests()) == 1

def test_refresh_order_oldest_strength_first(db, httpx_mock):
    upsert_institutions(db, HIPO + [OLD], ensure_source(db, "hipo"), "http://x")
    src = ensure_source(db, "openalex")
    db.execute("update institution set openalex_id = 'https://openalex.org/I' || id")
    for domain, ts in (("ntu.edu.tw", "2020-01-01"), ("old.ntu.tw", "2025-01-01")):
        db.execute("""insert into strength (institution_id, topic_id, topic_name, field_name, works_count, cited_by_count,
                      rank, source_id, source_url, fetched_at)
                      select id, 'T', 'T', 'F', 1, 0, 1, %s, 'u', %s from institution where domain=%s""", (src, ts, domain))
    httpx_mock.add_response(url=URL_RE, json={"results": []})
    assert run_job(OpenAlexJob(client=httpx.Client(), limit=1), db).status == "success"
    assert httpx_mock.get_requests()[0].url.params["search"] == "National Taiwan University"

def test_null_field_name_stored_as_unknown(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    data = json.loads(json.dumps(NTU)); data["results"][0]["topics"][0]["field"] = None
    httpx_mock.add_response(url=URL_RE, json=data)
    assert run_job(OpenAlexJob(client=httpx.Client()), db).status == "success"
    assert db.execute("select field_name from strength where rank=1").fetchone()[0] == "Unknown"

def test_ror_source_url_and_topic_order(db, httpx_mock):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, json=NTU)
    assert run_job(OpenAlexJob(client=httpx.Client(), api_key="k1"), db).status == "success"
    assert db.execute("select ror_id from institution where domain='ntu.edu.tw'").fetchone()[0] == NTU["results"][0]["ror"]
    rows = db.execute("select works_count, source_url from strength order by rank").fetchall()
    counts = [r[0] for r in rows]
    assert counts == sorted(counts, reverse=True)
    expected = sorted((t["count"] for t in NTU["results"][0]["topics"]), reverse=True)[:10]
    assert counts == expected
    assert all("api_key" not in u and "search=" in u for _, u in rows)

def test_all_requests_failing_marks_job_failed(db, httpx_mock, monkeypatch):
    monkeypatch.setattr("collegedata.jobs.openalex.time.sleep", lambda s: None)
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")
    httpx_mock.add_response(url=URL_RE, status_code=500, is_reusable=True)
    r = run_job(OpenAlexJob(client=httpx.Client()), db)
    assert r.status == "failed" and "OpenAlexAllFailed" in r.error

def test_checked_at_set_and_unchecked_come_first(db, httpx_mock, monkeypatch):
    monkeypatch.setattr("collegedata.jobs.openalex.time.sleep", lambda s: None)
    upsert_institutions(db, FIX_ALL, ensure_source(db, "hipo"), "http://x")
    db.execute("update institution set openalex_checked_at = now() - interval '1 day' where domain='ntu.edu.tw'")
    httpx_mock.add_response(url=URL_RE, json=NTU, is_reusable=True)
    run_job(OpenAlexJob(client=httpx.Client(), limit=2), db)
    assert db.execute("select openalex_checked_at from institution where domain='ntu.edu.tw'").fetchone()[0] < \
        db.execute("select min(openalex_checked_at) from institution where domain<>'ntu.edu.tw'").fetchone()[0]
