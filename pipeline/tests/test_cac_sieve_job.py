# tests/test_cac_sieve_job.py
import datetime, pathlib
from decimal import Decimal
import httpx, pytest
from collegedata.cac_http import CacFetcher
from collegedata.parsers.cac_sieve import SieveRow, SieveLevel, SieveParseResult
from collegedata.jobs.cac_sieve import CacSieveJob, target_years, parse_college_list, college_list_url, image_url
from collegedata.jobs.cac_common import Budget
from collegedata.runner import run_job

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
LIST = (FIX / "115_collegeList.htm").read_text(encoding="utf-8")
TODAY = datetime.date(2026, 10, 29)

def _row(code, name, gender=None, quota=23, school="001"):
    return SieveRow(school, code, gender, name, quota, "一般校系",
                    {"國文": "前標", "英文": "均標", "數學A": None, "數學B": None, "社會": None, "自然": None, "英聽": None},
                    {"國文": Decimal("3"), "英文": None, "數學A": None, "數學B": None, "社會": None, "自然": None, "學測科目組合": None},
                    {}, [SieveLevel(1, "社會10", ["社會"], Decimal("10"))], True, [])

def fake_parse(png, school_code, ocr=None):
    if school_code == "001":
        return SieveParseResult([_row("001012", "中國文學系"), _row("001082", "戲劇學系", "男", 8), _row("001082", "戲劇學系", "女", 9)], 0, [], ["一般校系"])
    return SieveParseResult([_row(school_code + "012", "某學系", school=school_code)], 0, [], ["一般校系"])

def _clock():
    t = [0.0]
    def now(): return t[0]
    def sleep(s): t[0] += s
    return now, sleep

def _job(years_html=None, **kw):
    now, sleep = _clock()
    f = CacFetcher(httpx.Client(), min_interval=0, sleep=sleep, clock=now)
    return CacSieveJob(today=TODAY, parse=kw.pop("parse", fake_parse), fetcher=f, budget=Budget(max_schools=kw.pop("max_schools", 10), time_budget=datetime.timedelta(minutes=75), started=0.0), **kw)

def _mock_year(httpx_mock, roc, html=LIST, pngs=("001",)):
    httpx_mock.add_response(url=college_list_url(roc), text=html, is_reusable=True)
    for c in pngs:
        httpx_mock.add_response(url=image_url(roc, c), content=b"png", is_reusable=True)

def test_target_years_roll_on_may_first():
    assert target_years(datetime.date(2027, 4, 30)) == [115, 114, 113]
    assert target_years(datetime.date(2027, 5, 1)) == [116, 115, 114]

def test_parse_college_list():
    lst = parse_college_list(LIST)
    assert len(lst) == 64 and lst[0] == ("001", "國立臺灣大學")

def test_writes_programs_requirement_and_sieve(db, httpx_mock):
    _mock_year(httpx_mock, 115, pngs=("001", "002"))
    for roc in (114, 113):
        _mock_year(httpx_mock, roc, pngs=())
    r = run_job(_job(max_schools=2), db)
    assert r.status == "success" and r.rows_written == 4
    rows = db.execute("""select p.name_zh, q.requirement, s.sieve, s.tiebreak, q.year, q.pathway, q.system_code
                         from admission_requirement q join program p on p.id = q.program_id
                         join admission_stat s on s.program_id = q.program_id and s.year = q.year and s.pathway = q.pathway
                         order by p.name_zh""").fetchall()
    assert [x[0] for x in rows] == ["中國文學系", "某學系", "戲劇學系(女)", "戲劇學系(男)"]
    req = rows[0][1]
    assert req["cac_code"] == "001012" and req["quota"] == 23 and req["thresholds"]["國文"] == "前標"
    assert req["sources"]["sieve_image"] == image_url(115, "001")
    assert rows[0][2] == [{"order": 1, "label": "社會10", "subjects": ["社會"], "min_score": "10"}]
    assert rows[0][3] == "同級分超額篩選" and rows[0][4:] == (2026, "tw_apply", "tw_gsat")
    done = db.execute("select roc_year, school_code, status, rows_written from cac_fetch order by roc_year desc, school_code").fetchall()
    assert done == [(115, "001", "done", 3), (115, "002", "done", 1)]   # 額度 2 所，最新學年優先

def test_done_units_are_not_refetched(db, httpx_mock):
    _mock_year(httpx_mock, 115, pngs=("001", "002", "003", "004"))
    for roc in (114, 113):
        _mock_year(httpx_mock, roc, pngs=())
    run_job(_job(max_schools=2), db)
    n_before = len(httpx_mock.get_requests())
    run_job(_job(max_schools=2), db)
    image_requests = [q for q in httpx_mock.get_requests()[n_before:] if q.url.path.endswith(".png")]
    assert {q.url.path.split("/")[-1] for q in image_requests} == {"003.png", "004.png"}

def test_busy_stops_run_but_keeps_finished_schools(db, httpx_mock):
    httpx_mock.add_response(url=college_list_url(115), text=LIST)
    httpx_mock.add_response(url=image_url(115, "001"), content=b"png")
    httpx_mock.add_response(url=image_url(115, "002"), text="流量過大，請稍後再試。")
    r = run_job(_job(max_schools=5), db)
    assert r.status == "success"
    assert db.execute("select status from cac_fetch where school_code='001'").fetchone() == ("done",)
    assert db.execute("select count(*) from cac_fetch where school_code='002'").fetchone() == (0,)
    assert not any(q.url.path.endswith("003.png") for q in httpx_mock.get_requests())

def test_parse_failure_marks_unit_failed_and_continues(db, httpx_mock):
    def bad_parse(png, school_code, ocr=None):
        if school_code == "001": raise ValueError("no table")
        return fake_parse(png, school_code)
    _mock_year(httpx_mock, 115, pngs=("001", "002"))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404)
    r = run_job(_job(max_schools=2, parse=bad_parse), db)
    assert r.status == "success" and r.rows_written == 1
    assert db.execute("select status, error from cac_fetch where school_code='001'").fetchone()[0] == "failed"
    assert "ValueError" in db.execute("select error from cac_fetch where school_code='001'").fetchone()[0]

def test_all_units_failed_fails_job(db, httpx_mock):
    def bad_parse(png, school_code, ocr=None): raise ValueError("x")
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    r = run_job(_job(max_schools=1, parse=bad_parse), db)
    assert r.status == "failed" and "all 1 units failed" in r.error

def test_newest_year_404_fails(db, httpx_mock):
    httpx_mock.add_response(url=college_list_url(115), status_code=404, is_reusable=True)
    r = run_job(_job(), db)
    assert r.status == "failed" and "404" in r.error

def test_high_skip_ratio_fails_unit(db, httpx_mock):
    def skippy(png, school_code, ocr=None): return SieveParseResult([_row("001012", "中國文學系")], 1, ["skip"], ["一般校系"])
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    r = run_job(_job(max_schools=1, parse=skippy), db)
    assert r.status == "failed"
    assert db.execute("select count(*) from admission_stat").fetchone() == (0,)

def test_rerun_merges_requirement_keeping_other_sources(db, httpx_mock):
    from collegedata.jobs.cac_common import merge_requirement
    _mock_year(httpx_mock, 115, pngs=("001",))
    for roc in (114, 113): httpx_mock.add_response(url=college_list_url(roc), status_code=404, is_reusable=True)
    run_job(_job(max_schools=1), db)
    pid, sid = db.execute("select p.id, p.source_id from program p where name_zh='中國文學系'").fetchone()
    merge_requirement(db, pid, 2026, {"stage2": {"stage1_pct": 20}, "sources": {"rules_page": "http://r"}}, sid, "http://r")
    req = db.execute("select requirement from admission_requirement where program_id=%s", (pid,)).fetchone()[0]
    assert req["stage2"] == {"stage1_pct": 20} and req["quota"] == 23
    assert req["sources"] == {"sieve_image": image_url(115, "001"), "rules_page": "http://r"}

def test_registered_in_runner():
    from collegedata.runner import REGISTRY
    assert "cac_sieve" in REGISTRY


def test_budget_from_env_treats_empty_as_unset(monkeypatch):
    monkeypatch.setenv("CAC_MAX_SCHOOLS", "")
    monkeypatch.setenv("CAC_TIME_BUDGET_MINUTES", "")
    b = Budget.from_env(clock=lambda: 5.0)
    assert b.max_schools == 10 and b.time_budget == datetime.timedelta(minutes=75) and b.started == 5.0
    monkeypatch.setenv("CAC_MAX_SCHOOLS", "3")
    assert Budget.from_env().max_schools == 3


def test_budget_exhausted_by_count_or_time():
    b = Budget(2, datetime.timedelta(minutes=1), 0.0)
    assert not b.exhausted(1, lambda: 59.0)
    assert b.exhausted(2, lambda: 0.0)
    assert b.exhausted(0, lambda: 60.0)
