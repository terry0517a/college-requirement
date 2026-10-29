# tests/test_cac_rules_job.py
import datetime, pathlib
import httpx, pytest
from collegedata.cac_http import CacFetcher
from collegedata.jobs.cac_common import Budget
from collegedata.jobs.cac_rules import CacRulesJob, target_year, query_url
from collegedata.runner import run_job

FIX = pathlib.Path(__file__).with_name("fixtures") / "cac"
SYS = "https://www.cac.edu.tw/apply115/system/ColQry_115xappLyfOrStu_Azd5gP29/"
QUERY = (FIX / "115_query.html").read_text(encoding="utf-8")
TOTAL = (FIX / "115_TotalGsdShow.htm").read_text(encoding="utf-8")
CODES = (FIX / "115_ShowGsd_code001.html").read_text(encoding="utf-8")
PAGE = (FIX / "115_001582.htm").read_text(encoding="utf-8")
ONE_CODE = '<a href="./html/115_001582.htm?v=1.0">詳細資料</a>'

def _job(today=datetime.date(2026, 10, 29), max_schools=10):
    t = [0.0]
    f = CacFetcher(httpx.Client(), min_interval=0, sleep=lambda s: t.__setitem__(0, t[0] + s), clock=lambda: t[0])
    return CacRulesJob(today=today, fetcher=f, budget=Budget(max_schools=max_schools, time_budget=datetime.timedelta(minutes=75), started=0.0, clock=lambda: t[0]))

def test_target_year_rolls_on_november_first():
    assert target_year(datetime.date(2026, 10, 31)) == 115
    assert target_year(datetime.date(2026, 11, 1)) == 116

def test_not_published_warns_in_november_and_fails_in_january(db, httpx_mock):
    httpx_mock.add_response(url=query_url(116), text="<html>nothing</html>", is_reusable=True)
    r = run_job(_job(today=datetime.date(2026, 11, 15)), db)
    assert r.status == "success" and r.rows_written == 0
    r = run_job(_job(today=datetime.date(2027, 1, 10)), db)
    assert r.status == "failed" and "NotPublishedYet" in r.error

def test_writes_stage2_and_program(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE)
    r = run_job(_job(max_schools=1), db)
    assert r.status == "success" and r.rows_written == 1
    row = db.execute("""select p.name_zh, q.requirement, q.source_url from admission_requirement q
                        join program p on p.id = q.program_id""").fetchone()
    assert row[0] == "資訊工程學系" and row[2] == SYS + "html/115_001582.htm?v=1.0"
    req = row[1]
    assert req["stage2"]["stage1_pct"] == 20 and req["stage2"]["items"][0] == {"name": "審查資料", "threshold": "70分", "pct": 50}
    assert req["thresholds"]["英文"] == "頂標" and req["multipliers"]["數學A"] == "2.5" and req["quota"] == 57
    assert req["sources"] == {"rules_page": SYS + "html/115_001582.htm?v=1.0"}
    assert db.execute("select status, rows_written from cac_fetch where job='cac_rules' and school_code='001'").fetchone() == ("done", 1)
    assert db.execute("select count(*) from admission_stat").fetchone() == (0,)
    post = next(q for q in httpx_mock.get_requests() if q.method == "POST")
    assert b"TxtGsdCode=001" in post.content and b"action=SubTxtGsdCode" in post.content

def test_merge_keeps_sieve_keys_written_earlier(db, httpx_mock):
    from collegedata.jobs.cac_common import merge_requirement, upsert_program
    from collegedata.jobs.uac import _institution_id, load_school_map
    from collegedata.sources import ensure_source
    sid = ensure_source(db, "cac")
    inst = _institution_id(db, {}, "國立臺灣大學", load_school_map(), sid, "u")
    pid = upsert_program(db, inst, "資訊工程學系", sid, "u")
    merge_requirement(db, pid, 2026, {"quota": 57, "thresholds": {"英文": "頂標"}, "group": "第一類組",
                                       "extra": {"note": "x"}, "sources": {"sieve_image": "img"}}, sid, "img")
    httpx_mock.add_response(url=query_url(115), text=QUERY)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE)
    assert run_job(_job(max_schools=1), db).status == "success"
    req = db.execute("select requirement from admission_requirement where program_id=%s", (pid,)).fetchone()[0]
    assert req["sources"] == {"sieve_image": "img", "rules_page": SYS + "html/115_001582.htm?v=1.0"}
    assert "stage2" in req and req["quota"] == 57
    assert req["group"] == "第一類組" and req["extra"] == {"note": "x"}
    assert db.execute("select count(*) from program").fetchone() == (1,)

def test_done_school_not_refetched_and_budget(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY, is_reusable=True)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL, is_reusable=True)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE, is_reusable=True)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE, is_reusable=True)
    run_job(_job(max_schools=1), db)
    n = len(httpx_mock.get_requests())
    run_job(_job(max_schools=1), db)   # 001 已 done → 處理 002
    posts = [q for q in httpx_mock.get_requests()[n:] if q.method == "POST"]
    assert len(posts) == 1 and b"TxtGsdCode=002" in posts[0].content

def test_busy_on_detail_page_stops_without_failing(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY, is_reusable=True)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL, is_reusable=True)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE, is_reusable=True)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text="流量過大，請稍後再試。", is_reusable=True)
    r = run_job(_job(max_schools=3), db)   # runner 會重試一次，mock 需可重用
    assert r.status == "failed"   # 嘗試 1 所、成功 0 所
    assert db.execute("select count(*) from cac_fetch").fetchone() == (0,)

def test_registered_in_runner():
    from collegedata.runner import REGISTRY
    assert "cac_rules" in REGISTRY


def test_school_with_only_unparseable_pages_is_not_success(db, httpx_mock):
    httpx_mock.add_response(url=query_url(115), text=QUERY, is_reusable=True)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL, is_reusable=True)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=ONE_CODE, is_reusable=True)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text="<html>not a rules page</html>", is_reusable=True)
    r = run_job(_job(max_schools=1), db)
    assert r.status == "failed" and "all 1 units failed" in r.error   # not counted as done
    assert db.execute("select count(*) from program").fetchone() == (0,)
    assert db.execute("select count(*) from admission_requirement").fetchone() == (0,)


def test_partial_skip_school_is_done_with_rows_skipped(db, httpx_mock):
    two = ONE_CODE + '<a href="./html/115_001583.htm?v=1.0">詳細資料</a>'
    httpx_mock.add_response(url=query_url(115), text=QUERY)
    httpx_mock.add_response(url=SYS + "TotalGsdShow.htm", text=TOTAL)
    httpx_mock.add_response(url=SYS + "ShowGsd.php", method="POST", text=two)
    httpx_mock.add_response(url=SYS + "html/115_001582.htm?v=1.0", text=PAGE)
    httpx_mock.add_response(url=SYS + "html/115_001583.htm?v=1.0", text="<html>not a rules page</html>")
    r = run_job(_job(max_schools=1), db)
    assert r.status == "success" and r.rows_written == 1
    assert db.execute("select status, rows_written, rows_skipped from cac_fetch where school_code='001'").fetchone() == ("done", 1, 1)
