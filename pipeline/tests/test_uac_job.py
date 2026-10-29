import json, pathlib, pytest, httpx
from collegedata.jobs.hipo import upsert_institutions
from collegedata.jobs.uac import UacJob, UnknownSchoolError
from collegedata.sources import ensure_source
from collegedata.runner import run_job

FIXDIR = pathlib.Path(__file__).with_name("fixtures")
PDF = (FIXDIR / "uac_115_p1-2.pdf").read_bytes()
HIPO = json.loads((FIXDIR / "hipo_sample.json").read_text())

def _seed(db):
    upsert_institutions(db, HIPO, ensure_source(db, "hipo"), "http://x")

def test_writes_programs_and_stats(db, httpx_mock):
    _seed(db)
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF)
    r = run_job(UacJob(client=httpx.Client(), years=[115]), db)
    assert r.status == "success" and r.rows_written > 30
    row = db.execute("""select i.name_zh, p.name_zh, s.year, s.pathway, s.min_score, s.admitted_count, s.subjects, s.tiebreak
                        from admission_stat s join program p on p.id=s.program_id join institution i on i.id=p.institution_id
                        where p.name_zh='中國文學系'""").fetchone()
    assert row[:6] == ("國立臺灣大學", "中國文學系", 2026, "tw_distribution", 265.5, 19)
    assert row[6][0] == {"subject": "國", "weight": 1.5} and row[7] == "國 50"

def test_creates_institution_missing_from_hipo(db, httpx_mock):
    # 不先 _seed：institution 表為空，Job 須自行建立學校
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF)
    assert run_job(UacJob(client=httpx.Client(), years=[115]), db).status == "success"
    row = db.execute("select name_en, name_zh, country_code, web_url from institution where domain='ntu.edu.tw'").fetchone()
    assert row == ("National Taiwan University", "國立臺灣大學", "TW", "https://www.ntu.edu.tw/")

def test_rerun_is_idempotent(db, httpx_mock):
    _seed(db)
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF, is_reusable=True)
    n1 = run_job(UacJob(client=httpx.Client(), years=[115]), db).rows_written
    n2 = run_job(UacJob(client=httpx.Client(), years=[115]), db).rows_written
    assert n1 == n2 == db.execute("select count(*) from admission_stat").fetchone()[0]

def test_unknown_school_fails_loudly(db, httpx_mock, tmp_path, monkeypatch):
    _seed(db)
    monkeypatch.setattr("collegedata.jobs.uac.load_school_map", lambda: {})  # 空對應表
    httpx_mock.add_response(url="https://www2.uac.edu.tw/115data/115_result_school_data.pdf", content=PDF, is_reusable=True)  # runner retries
    r = run_job(UacJob(client=httpx.Client(), years=[115]), db)
    assert r.status == "failed" and "國立臺灣大學" in r.error
    assert db.execute("select count(*) from admission_stat").fetchone()[0] == 0
