import pathlib, pytest
from collegedata.parsers.uac import parse_uac_pdf, parse_subjects

FIX = pathlib.Path(__file__).with_name("fixtures") / "uac_115_p1-2.pdf"

def test_parse_subjects():
    assert parse_subjects("國x1.50 英x1.25 數Bx1.00") == [("國",1.5),("英",1.25),("數B",1.0)]

def test_parse_subjects_rejects_unknown():
    with pytest.raises(ValueError):
        parse_subjects("火x1.00")

def test_first_row():
    rows = parse_uac_pdf(FIX)
    r = rows[0]
    assert (r.code, r.school_zh, r.program_zh) == ("0001", "國立臺灣大學", "中國文學系")
    assert r.subjects == [("國",1.5),("英",1.25),("歷",1.25),("地",1.0)]
    assert (r.admitted_count, r.min_score, r.tiebreak) == (19, 265.5, "國 50")

def test_empty_tiebreak_is_none():
    r = next(x for x in parse_uac_pdf(FIX) if x.code == "0004")
    assert r.tiebreak is None and r.min_score == 205.0

def test_no_score_row_keeps_null_score_and_zero_admitted():
    from collegedata.parsers.uac import row_from_cells
    r = row_from_cells(['1227','中國文化大學','廣告學系B組','術x1.00 國x1.00 公x1.00','0','-----','','-----','-----','-----','-----','-----'])
    assert (r.min_score, r.admitted_count, r.tiebreak) == (None, 0, None)

def test_header_rows_skipped_and_pages_concatenated():
    rows = parse_uac_pdf(FIX)
    assert all(r.code.isdigit() for r in rows)
    assert any(r.code == "0040" for r in rows)   # 第 2 頁第一列
