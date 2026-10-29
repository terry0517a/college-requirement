import datetime
import json
import pathlib
import re
from decimal import Decimal

import httpx
import pytest

from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.scorecard import ScorecardJob
from collegedata.runner import run_job
from collegedata.sources import ensure_source

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
SAMPLE = json.loads((FIXDIR / "scorecard_sample.json").read_text())
HIPO_STANFORD = [r for r in json.loads((FIXDIR / "hipo_sample.json").read_text())
                 if r["domains"][0] == "stanford.edu"]
TODAY = datetime.date(2026, 10, 29)
TABLES = ("institution", "program", "admission_stat", "admission_requirement", "cost", "institution_stat")


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch):
    monkeypatch.setattr("collegedata.jobs.scorecard.time.sleep", lambda s: None)


def probe(httpx_mock, y, total):
    httpx_mock.add_response(
        url=re.compile(rf".*{y}\.admissions\.admission_rate\.overall__range=.*per_page=1.*"),
        json={"metadata": {"total": total}, "results": []}, is_reusable=True)


def page(httpx_mock, **kw):
    kw.setdefault("json", SAMPLE)
    httpx_mock.add_response(url=re.compile(r".*per_page=100.*"), is_reusable=True, **kw)


def latest_2024(httpx_mock):
    probe(httpx_mock, 2026, 0)
    probe(httpx_mock, 2025, 0)
    probe(httpx_mock, 2024, 3)


def counts(db):
    return {t: db.execute(f"select count(*) from {t}").fetchone()[0] for t in TABLES}


def test_probes_latest_year_skipping_empty_years(db, httpx_mock):
    latest_2024(httpx_mock)
    page(httpx_mock)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "success" and r.rows_written == 3
    years = {x[0] for x in db.execute("select distinct year from admission_stat")}
    assert years == {2024, 2023, 2022}
    for t in TABLES:
        urls = db.execute(f"select distinct source_url from {t}").fetchall()
        assert urls and all("api_key" not in u for (u,) in urls)
    rows = db.execute("select scorecard_id, source_url from institution where scorecard_id is not null").fetchall()
    assert len(rows) == 3
    assert all(u == f"https://collegescorecard.ed.gov/school/?{sid}" for sid, u in rows)
    stanford_urls = {x[0] for x in db.execute(
        """select p.source_url from program p join institution i on i.id=p.institution_id where i.scorecard_id=243744
           union select c.source_url from cost c join institution i on i.id=c.institution_id where i.scorecard_id=243744
           union select s.source_url from institution_stat s join institution i on i.id=s.institution_id
                 where i.scorecard_id=243744
           union select r.source_url from admission_requirement r join program p on p.id=r.program_id
                 join institution i on i.id=p.institution_id where i.scorecard_id=243744
           union select a.source_url from admission_stat a join program p on p.id=a.program_id
                 join institution i on i.id=p.institution_id where i.scorecard_id=243744""")}
    assert stanford_urls == {"https://collegescorecard.ed.gov/school/?243744"}
    reqs = httpx_mock.get_requests()
    assert all(q.url.params["api_key"] == "k1" for q in reqs)
    assert len(reqs) == 4  # 2026, 2025, 2024 probes + one page


def test_fails_when_no_year_has_data(db, httpx_mock):
    for y in range(2026, 2020, -1):
        probe(httpx_mock, y, 0)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "failed" and "ScorecardDataError" in r.error
    assert db.execute("select count(*) from institution").fetchone()[0] == 0
    probed = {q.url.params.get("per_page") for q in httpx_mock.get_requests()}
    assert probed == {"1"}  # never reached paging
    assert len(httpx_mock.get_requests()) == 12  # six probes, run retried once


def test_writes_requirement_stat_cost_programs_for_stanford(db, httpx_mock):
    latest_2024(httpx_mock)
    page(httpx_mock)
    assert run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db).status == "success"
    iid = db.execute("select id from institution where scorecard_id=243744").fetchone()[0]
    assert db.execute("select name_en, domain, control, city, region from institution where id=%s", (iid,)).fetchone() \
        == ("Stanford University", "stanford.edu", "private", "Stanford", "CA")
    codes = {x[0] for x in db.execute("select code from program where institution_id=%s", (iid,))}
    assert codes == {"all", "11", "14", "26", "27", "54"}
    assert db.execute("select field_code from program where institution_id=%s and code='11'", (iid,)).fetchone()[0] == "cs"
    req = db.execute("""select r.requirement from admission_requirement r join program p on p.id=r.program_id
                        where p.institution_id=%s and r.year=2024""", (iid,)).fetchone()[0]
    assert req["sat"]["total"] == {"p25": 1510, "p75": 1580} and req["act"]["composite"] == {"p25": 34, "p75": 35}
    assert req["sat"]["rw"] == {"p25": 740, "p75": 780} and req["sat"]["math"] == {"p25": 770, "p75": 800}
    rate = db.execute("""select s.admission_rate, s.admitted_count from admission_stat s join program p on p.id=s.program_id
                         where p.institution_id=%s and s.year=2024 and s.pathway='us_freshman'""", (iid,)).fetchone()
    assert float(rate[0]) == 0.0361 and rate[1] is None
    costs = dict(db.execute("select residency, tuition from cost where institution_id=%s and year=2024", (iid,)).fetchall())
    assert costs == {"local": 68544, "out_of_state": 68544}
    st = db.execute("select student_size, completion_rate, median_earnings from institution_stat where institution_id=%s and year=2024", (iid,)).fetchone()
    assert st == (7554, Decimal("0.9164"), Decimal("125340"))


def test_no_requirement_when_scores_missing_but_rate_kept(db, httpx_mock):
    latest_2024(httpx_mock)
    page(httpx_mock)
    assert run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db).status == "success"
    iid = db.execute("select id from institution where scorecard_id=900001").fetchone()[0]
    assert db.execute("select count(*) from admission_requirement r join program p on p.id=r.program_id where p.institution_id=%s", (iid,)).fetchone()[0] == 0
    assert db.execute("select count(*) from admission_stat s join program p on p.id=s.program_id where p.institution_id=%s", (iid,)).fetchone()[0] == 3
    assert db.execute("select count(*) from institution_stat where institution_id=%s", (iid,)).fetchone()[0] == 3


def test_null_url_and_domain_collision_do_not_merge(db, httpx_mock):
    upsert_institutions(db, HIPO_STANFORD, ensure_source(db, "hipo"), "http://x")
    db.execute("""insert into institution (country_code, name_en, domain, scorecard_id, source_id, source_url, fetched_at)
                  values ('US', 'Other College', 'testoptional.edu', 123, %s, 'http://x', now())""",
               (ensure_source(db, "hipo"),))
    latest_2024(httpx_mock)
    page(httpx_mock)
    assert run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db).status == "success"
    assert db.execute("select count(*) from institution where domain='stanford.edu'").fetchone()[0] == 1
    assert db.execute("select scorecard_id from institution where domain='stanford.edu'").fetchone()[0] == 243744
    assert db.execute("select domain from institution where scorecard_id=900001").fetchone()[0] == "testoptional.edu#900001"
    assert db.execute("select domain from institution where scorecard_id=900002").fetchone()[0] == "scorecard#900002"
    assert db.execute("select name_en from institution where scorecard_id=123").fetchone()[0] == "Other College"


def test_rerun_is_idempotent(db, httpx_mock):
    latest_2024(httpx_mock)
    page(httpx_mock)
    assert run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db).status == "success"
    counts_after_first = counts(db)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "success" and r.rows_written == 3
    counts_after_second = counts(db)
    for table in TABLES:
        assert counts_after_first[table] == counts_after_second[table]


def test_limit_stops_early_and_http_error_fails(db, httpx_mock):
    latest_2024(httpx_mock)
    page(httpx_mock)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY, limit=1), db)
    assert r.status == "success" and r.rows_written == 1
    assert db.execute("select count(*) from institution where scorecard_id is not null").fetchone()[0] == 1

    httpx_mock.reset()
    latest_2024(httpx_mock)
    page(httpx_mock, status_code=429, json=None)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "failed" and "429" in r.error
    assert "k1" not in r.error and "api_key" not in r.error
    assert len(r.error) < 200


def test_missing_api_key_fails_without_requests(db, httpx_mock):
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="", today=TODAY), db)
    assert r.status == "failed"
    assert r.error == "ScorecardConfigError: SCORECARD_API_KEY is not set"
    assert httpx_mock.get_requests() == []


def _record(base: dict, **changes) -> dict:
    rec = json.loads(json.dumps(base))
    rec.update(changes)
    return rec


def test_implausible_coverage_fails_and_writes_nothing(db, httpx_mock):
    blank = {k: None for k in SAMPLE["results"][1]
             if k.split(".", 1)[0].isdigit() and ("_scores." in k or ".tuition." in k)}
    results = [_record(SAMPLE["results"][1], id=800000 + i, **blank) for i in range(100)]
    latest_2024(httpx_mock)
    page(httpx_mock, json={"metadata": {"page": 0, "total": 100, "per_page": 100}, "results": results})
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "failed" and "ScorecardDataError" in r.error
    assert "2024" in r.error
    assert db.execute("select count(*) from institution").fetchone()[0] == 0


def test_out_of_range_values_stored_as_null(db, httpx_mock):
    bad = _record(SAMPLE["results"][0], **{
        "2024.admissions.admission_rate.overall": 1.5,
        "2024.admissions.sat_scores.25th_percentile.math": 100,
    })
    latest_2024(httpx_mock)
    page(httpx_mock, json={**SAMPLE, "results": [bad, *SAMPLE["results"][1:]]})
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "success"
    iid = db.execute("select id from institution where scorecard_id=243744").fetchone()[0]
    rates = db.execute("""select s.admission_rate from admission_stat s join program p on p.id=s.program_id
                          where p.institution_id=%s and s.year=2024""", (iid,)).fetchall()
    assert all(rate is None for (rate,) in rates)
    req = db.execute("""select r.requirement from admission_requirement r join program p on p.id=r.program_id
                        where p.institution_id=%s and r.year=2024""", (iid,)).fetchone()[0]
    assert req["sat"]["math"] is None and req["sat"]["total"] is None
    assert req["sat"]["rw"] == {"p25": 740, "p75": 780}


def test_one_second_between_every_request_including_retry(db, httpx_mock, monkeypatch):
    # Each sleep records how many requests had gone out when it was called.
    sleeps = []
    monkeypatch.setattr("collegedata.jobs.scorecard.time.sleep",
                        lambda s: sleeps.append((s, len(httpx_mock.get_requests()))))
    latest_2024(httpx_mock)
    page(httpx_mock, status_code=429, json=None)
    r = run_job(ScorecardJob(client=httpx.Client(), api_key="k1", today=TODAY), db)
    assert r.status == "failed" and "429" in r.error
    n = len(httpx_mock.get_requests())
    assert n == 8  # (3 probes + 1 page) x 2 attempts
    assert sleeps == [(1, k) for k in range(1, n)]
